"""Contrato HTTP da consulta autenticada da trilha de auditoria."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from crm_api.application.audit.list_audit_events import ListAuditEventsUseCase
from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditEvent,
    AuditEventCursor,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.auth.entities import User
from crm_api.main import app
from crm_api.presentation.audit import dependencies as audit_dependencies
from crm_api.presentation.auth import dependencies as auth_dependencies

OWNER_ID = UUID("00000000-0000-0000-0000-000000000017")
OWNER = User(
    id=OWNER_ID,
    email="owner@deltaforce.internal",
    full_name="Owner Synthetic",
    password_hash="not-returned",
    is_active=True,
)


@dataclass
class MemoryAuditRepository:
    events: list[AuditEvent] = field(default_factory=list)

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)

    async def list_recent(
        self, *, limit: int, before: AuditEventCursor | None
    ) -> list[AuditEvent]:
        ordered = sorted(
            self.events,
            key=lambda event: (event.occurred_at, event.id),
            reverse=True,
        )
        if before is not None:
            ordered = [
                event
                for event in ordered
                if (event.occurred_at, event.id) < (before.occurred_at, before.id)
            ]
        return ordered[:limit]


@dataclass
class SpyTransaction:
    commit_calls: int = 0
    rollback_calls: int = 0

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


@pytest.fixture
def audit_client() -> (
    Iterator[tuple[TestClient, MemoryAuditRepository, SpyTransaction]]
):
    occurred_at = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    repository = MemoryAuditRepository(
        events=[
            AuditEvent(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                occurred_at=occurred_at,
                actor_kind=AuditActorKind.ANONYMOUS,
                actor_user_id=None,
                action=AuditAction.LOGIN,
                resource_type=AuditResourceType.OWNER_ACCOUNT,
                resource_id=None,
                result=AuditResult.DENIED,
                context={"reason_code": "invalid_credentials"},
            ),
            AuditEvent(
                id=UUID("00000000-0000-0000-0000-000000000002"),
                occurred_at=occurred_at + timedelta(seconds=1),
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=OWNER_ID,
                action=AuditAction.LOGIN,
                resource_type=AuditResourceType.OWNER_ACCOUNT,
                resource_id=str(OWNER_ID),
                result=AuditResult.SUCCESS,
                context={},
            ),
        ]
    )
    transaction = SpyTransaction()
    recorder = RecordAuditEventUseCase(events=repository)

    app.dependency_overrides[auth_dependencies.get_current_user] = lambda: OWNER
    app.dependency_overrides[audit_dependencies.get_list_audit_events_use_case] = (
        lambda: ListAuditEventsUseCase(
            events=repository,
            audit=recorder,
            transaction=transaction,
        )
    )

    try:
        with TestClient(app) as client:
            yield client, repository, transaction
    finally:
        app.dependency_overrides.clear()


def test_owner_lists_sanitized_events_with_stable_pagination(
    audit_client: tuple[TestClient, MemoryAuditRepository, SpyTransaction],
) -> None:
    client, repository, transaction = audit_client

    response = client.get("/audit/events?limit=1")

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0] == {
        "id": "00000000-0000-0000-0000-000000000002",
        "occurred_at": "2026-08-20T12:00:01Z",
        "actor_kind": "authenticated",
        "actor_user_id": str(OWNER_ID),
        "action": "auth.login",
        "resource_type": "owner_account",
        "resource_id": str(OWNER_ID),
        "result": "success",
        "context": {},
    }
    assert body["next_cursor"] == {
        "occurred_at": "2026-08-20T12:00:01Z",
        "id": "00000000-0000-0000-0000-000000000002",
    }
    assert transaction.commit_calls == 1
    assert transaction.rollback_calls == 0
    assert repository.events[-1].action == "audit.log_view"
    assert repository.events[-1].actor_user_id == OWNER_ID
    assert repository.events[-1].context == {}


@pytest.mark.parametrize(
    "query",
    ("limit=0", "limit=101"),
)
def test_audit_pagination_rejects_out_of_range_values(
    audit_client: tuple[TestClient, MemoryAuditRepository, SpyTransaction],
    query: str,
) -> None:
    client, repository, transaction = audit_client
    initial_event_count = len(repository.events)

    response = client.get(f"/audit/events?{query}")

    assert response.status_code == 422
    assert len(repository.events) == initial_event_count
    assert transaction.commit_calls == 0
    assert transaction.rollback_calls == 0


@pytest.mark.parametrize(
    "params",
    [
        {"before_id": "00000000-0000-0000-0000-000000000002"},
        {"before_occurred_at": "2026-08-20T12:00:01Z"},
        {
            "before_occurred_at": "2026-08-20T12:00:01",
            "before_id": "00000000-0000-0000-0000-000000000002",
        },
    ],
)
def test_invalid_cursor_is_rejected_without_recording_a_view(
    audit_client: tuple[TestClient, MemoryAuditRepository, SpyTransaction],
    params: dict[str, str],
) -> None:
    client, repository, transaction = audit_client
    initial_event_count = len(repository.events)

    response = client.get("/audit/events", params=params)

    assert response.status_code == 422
    assert len(repository.events) == initial_event_count
    assert transaction.commit_calls == 0


def test_cursor_prevents_view_event_from_shifting_the_next_page(
    audit_client: tuple[TestClient, MemoryAuditRepository, SpyTransaction],
) -> None:
    client, repository, transaction = audit_client

    first_page = client.get("/audit/events", params={"limit": 1})
    cursor = first_page.json()["next_cursor"]
    second_page = client.get(
        "/audit/events",
        params={
            "limit": 1,
            "before_occurred_at": cursor["occurred_at"],
            "before_id": cursor["id"],
        },
    )

    first_id = first_page.json()["items"][0]["id"]
    second_id = second_page.json()["items"][0]["id"]
    assert first_id == "00000000-0000-0000-0000-000000000002"
    assert second_id == "00000000-0000-0000-0000-000000000001"
    assert first_id != second_id
    assert second_page.json()["next_cursor"] is None
    assert [event.action for event in repository.events].count("audit.log_view") == 2
    assert transaction.commit_calls == 2


def test_audit_response_never_exposes_authentication_material(
    audit_client: tuple[TestClient, MemoryAuditRepository, SpyTransaction],
) -> None:
    client, _, _ = audit_client

    response = client.get("/audit/events")

    serialized = response.text.lower()
    assert "password" not in serialized
    assert "session_token" not in serialized
    assert "authorization" not in serialized
    assert OWNER.email not in serialized
    assert OWNER.password_hash not in serialized
    assert "raw-session-secret" not in serialized
