from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import pytest

from crm_api.application.audit.list_audit_events import ListAuditEventsUseCase
from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditEvent,
    AuditEventCursor,
    AuditResult,
)


@dataclass
class RecordingAuditEventRepository:
    recent_events: list[AuditEvent] = field(default_factory=list)
    appended_events: list[AuditEvent] = field(default_factory=list)
    requested_pages: list[
        tuple[
            int,
            AuditEventCursor | None,
            AuditAction | None,
            AuditResult | None,
        ]
    ] = field(default_factory=list)

    async def append(self, event: AuditEvent) -> None:
        self.appended_events.append(event)

    async def list_recent(
        self,
        *,
        limit: int,
        before: AuditEventCursor | None,
        action: AuditAction | None,
        result: AuditResult | None,
    ) -> list[AuditEvent]:
        self.requested_pages.append((limit, before, action, result))
        return self.recent_events


@dataclass
class SpyTransaction:
    commit_calls: int = 0
    rollback_calls: int = 0

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


def build_use_case(
    repository: RecordingAuditEventRepository,
    transaction: SpyTransaction,
) -> ListAuditEventsUseCase:
    return ListAuditEventsUseCase(
        events=repository,
        audit=RecordAuditEventUseCase(events=repository),
        transaction=transaction,
    )


async def test_delegates_cursor_page_and_audits_the_view() -> None:
    repository = RecordingAuditEventRepository()
    transaction = SpyTransaction()
    use_case = build_use_case(repository, transaction)
    cursor = AuditEventCursor(
        occurred_at=datetime(2026, 8, 20, tzinfo=UTC),
        id=UUID("00000000-0000-0000-0000-000000000001"),
    )
    actor_id = UUID("00000000-0000-0000-0000-000000000017")

    result = await use_case.execute(
        actor_user_id=actor_id,
        limit=25,
        before=cursor,
        action=AuditAction.LOGIN,
        result=AuditResult.SUCCESS,
    )

    assert result.items == ()
    assert result.next_cursor is None
    assert repository.requested_pages == [
        (26, cursor, AuditAction.LOGIN, AuditResult.SUCCESS)
    ]
    assert [event.action for event in repository.appended_events] == ["audit.log_view"]
    assert repository.appended_events[0].actor_user_id == actor_id
    assert transaction.commit_calls == 1
    assert transaction.rollback_calls == 0


@pytest.mark.parametrize("limit", [0, 101])
async def test_rejects_limit_outside_application_boundary(limit: int) -> None:
    repository = RecordingAuditEventRepository()
    transaction = SpyTransaction()
    use_case = build_use_case(repository, transaction)

    with pytest.raises(ValueError, match="limit"):
        await use_case.execute(
            actor_user_id=UUID("00000000-0000-0000-0000-000000000017"),
            limit=limit,
            before=None,
        )

    assert repository.requested_pages == []
    assert repository.appended_events == []
    assert transaction.commit_calls == 0
    assert transaction.rollback_calls == 0


@pytest.mark.parametrize(
    ("filter_name", "filter_value"),
    [("action", "auth.login"), ("result", "success")],
)
async def test_rejects_non_enum_filters(filter_name: str, filter_value: str) -> None:
    repository = RecordingAuditEventRepository()
    transaction = SpyTransaction()
    use_case = build_use_case(repository, transaction)
    filters = {filter_name: filter_value}

    with pytest.raises(ValueError, match=filter_name):
        await use_case.execute(
            actor_user_id=UUID("00000000-0000-0000-0000-000000000017"),
            limit=25,
            before=None,
            **filters,  # type: ignore[arg-type]
        )

    assert repository.requested_pages == []
    assert repository.appended_events == []
    assert transaction.commit_calls == 0
    assert transaction.rollback_calls == 0
