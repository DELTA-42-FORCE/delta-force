from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditEvent,
    AuditEventCursor,
    AuditResourceType,
    AuditResult,
)


@dataclass
class FakeAuditEventRepository:
    events: list[AuditEvent] = field(default_factory=list)

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)

    async def list_recent(
        self, *, limit: int, before: AuditEventCursor | None
    ) -> list[AuditEvent]:
        return self.events


def _valid_input() -> dict[str, Any]:
    owner_id = uuid4()
    return {
        "actor_kind": AuditActorKind.AUTHENTICATED,
        "actor_user_id": owner_id,
        "action": AuditAction.OWNER_PROFILE_VIEW,
        "resource_type": AuditResourceType.OWNER_ACCOUNT,
        "resource_id": str(owner_id),
        "result": AuditResult.SUCCESS,
        "context": {
            "route_template": "/clients/{client_id}",
            "http_method": "GET",
            "reason_code": "invalid_credentials",
        },
    }


async def test_records_a_valid_event_with_uuid_and_utc_timestamp() -> None:
    repository = FakeAuditEventRepository()
    use_case = RecordAuditEventUseCase(events=repository)
    before = datetime.now(UTC)

    event = await use_case.execute(**_valid_input())

    after = datetime.now(UTC)
    assert isinstance(event.id, UUID)
    assert before <= event.occurred_at <= after
    assert event.occurred_at.utcoffset() is not None
    assert event.occurred_at.utcoffset().total_seconds() == 0
    assert repository.events == [event]


@pytest.mark.parametrize(
    ("actor_kind", "actor_user_id"),
    [
        (AuditActorKind.AUTHENTICATED, None),
        (AuditActorKind.ANONYMOUS, uuid4()),
    ],
)
async def test_rejects_incoherent_actor_identity(
    actor_kind: AuditActorKind, actor_user_id: UUID | None
) -> None:
    repository = FakeAuditEventRepository()
    use_case = RecordAuditEventUseCase(events=repository)
    audit_input = _valid_input()
    audit_input.update(actor_kind=actor_kind, actor_user_id=actor_user_id)

    with pytest.raises(ValueError, match="actor"):
        await use_case.execute(**audit_input)

    assert repository.events == []


async def test_authenticated_actor_requires_a_uuid_value() -> None:
    repository = FakeAuditEventRepository()
    use_case = RecordAuditEventUseCase(events=repository)
    audit_input = _valid_input()
    audit_input["actor_user_id"] = "not-a-uuid"

    with pytest.raises(ValueError, match="actor"):
        await use_case.execute(**audit_input)

    assert repository.events == []


@pytest.mark.parametrize("field_name", ["action", "resource_type", "resource_id"])
@pytest.mark.parametrize("empty_value", ["", "   "])
async def test_rejects_empty_action_and_resource_fields(
    field_name: str, empty_value: str
) -> None:
    repository = FakeAuditEventRepository()
    use_case = RecordAuditEventUseCase(events=repository)
    audit_input = _valid_input()
    audit_input[field_name] = empty_value

    with pytest.raises(ValueError, match=field_name):
        await use_case.execute(**audit_input)

    assert repository.events == []


@pytest.mark.parametrize(
    ("field_name", "sensitive_value"),
    [
        ("action", "person@example.com"),
        ("resource_type", "raw-session-secret"),
        ("result", "raw-session-secret"),
        ("resource_id", "123.456.789-00"),
        ("resource_id", "person@example.com"),
        ("resource_id", "A" * 128),
    ],
)
async def test_rejects_sensitive_values_in_catalog_and_resource_fields(
    field_name: str,
    sensitive_value: str,
) -> None:
    repository = FakeAuditEventRepository()
    use_case = RecordAuditEventUseCase(events=repository)
    audit_input = _valid_input()
    audit_input[field_name] = sensitive_value

    with pytest.raises(ValueError, match=field_name):
        await use_case.execute(**audit_input)

    assert repository.events == []


async def test_resource_id_can_be_omitted_for_resource_wide_events() -> None:
    repository = FakeAuditEventRepository()
    use_case = RecordAuditEventUseCase(events=repository)
    audit_input = _valid_input()
    audit_input["resource_id"] = None

    event = await use_case.execute(**audit_input)

    assert event.resource_id is None


@pytest.mark.parametrize(
    "sensitive_key",
    ["password", "authorization", "session_token", "document_content"],
)
async def test_rejects_secret_or_other_non_allowlisted_context_keys(
    sensitive_key: str,
) -> None:
    repository = FakeAuditEventRepository()
    use_case = RecordAuditEventUseCase(events=repository)
    audit_input = _valid_input()
    audit_input["context"] = {sensitive_key: "must-not-be-recorded"}

    with pytest.raises(ValueError, match="context"):
        await use_case.execute(**audit_input)

    assert repository.events == []


@pytest.mark.parametrize(
    "invalid_context",
    [
        {"reason_code": "raw-session-secret"},
        {"reason_code": "person@example.com"},
        {"http_method": "GET raw-session-secret"},
        {"route_template": "/clients?email=person@example.com"},
        {"route_template": "not-a-server-route"},
        {"route_template": "/" + "a" * 128},
        {"reason_code": 17},
    ],
)
async def test_rejects_unbounded_or_sensitive_context_values(
    invalid_context: dict[str, Any],
) -> None:
    repository = FakeAuditEventRepository()
    use_case = RecordAuditEventUseCase(events=repository)
    audit_input = _valid_input()
    audit_input["context"] = invalid_context

    with pytest.raises(ValueError, match="context"):
        await use_case.execute(**audit_input)

    assert repository.events == []


async def test_anonymous_event_without_user_id_is_valid() -> None:
    repository = FakeAuditEventRepository()
    use_case = RecordAuditEventUseCase(events=repository)
    audit_input = _valid_input()
    audit_input.update(
        actor_kind=AuditActorKind.ANONYMOUS,
        actor_user_id=None,
        result=AuditResult.DENIED,
    )

    event = await use_case.execute(**audit_input)

    assert event.actor_kind is AuditActorKind.ANONYMOUS
    assert event.actor_user_id is None
    assert event.result is AuditResult.DENIED


async def test_omitted_context_is_stored_as_an_empty_mapping() -> None:
    repository = FakeAuditEventRepository()
    use_case = RecordAuditEventUseCase(events=repository)
    audit_input = _valid_input()
    del audit_input["context"]

    event = await use_case.execute(**audit_input)

    assert event.context == {}
