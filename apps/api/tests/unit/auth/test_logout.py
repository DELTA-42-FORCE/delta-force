from datetime import UTC, datetime, timedelta
from uuid import uuid4

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.auth.logout import LogoutUseCase
from crm_api.domain.auth.entities import Session
from fakes import (
    FakeAuditEventRepository,
    FakeSessionRepository,
    FakeSessionTokenHasher,
    FakeTransaction,
)


def _build_logout(
    sessions: FakeSessionRepository,
) -> tuple[LogoutUseCase, FakeAuditEventRepository, FakeTransaction]:
    audit_events = FakeAuditEventRepository()
    transaction = FakeTransaction()
    return (
        LogoutUseCase(
            sessions=sessions,
            token_hasher=FakeSessionTokenHasher(),
            audit=RecordAuditEventUseCase(events=audit_events),
            transaction=transaction,
        ),
        audit_events,
        transaction,
    )


async def test_logout_revokes_the_session_so_it_can_no_longer_be_used() -> None:
    session = Session(
        token_hash="hashed:token-to-revoke",
        user_id=uuid4(),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        revoked_at=None,
    )
    sessions = FakeSessionRepository({session.token_hash: session})
    use_case, audit_events, transaction = _build_logout(sessions)

    await use_case.execute(
        session_token="token-to-revoke", actor_user_id=session.user_id
    )

    assert sessions.sessions["hashed:token-to-revoke"].revoked_at is not None
    assert [event.action for event in audit_events.events] == ["auth.logout"]
    assert transaction.commit_calls == 1


async def test_logout_of_unknown_token_is_a_no_op() -> None:
    sessions = FakeSessionRepository()
    use_case, audit_events, transaction = _build_logout(sessions)
    actor_user_id = uuid4()

    await use_case.execute(session_token="never-issued", actor_user_id=actor_user_id)

    assert sessions.sessions == {}
    assert audit_events.events[0].actor_user_id == actor_user_id
    assert transaction.commit_calls == 1
