from datetime import timedelta

import pytest

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.auth.session_issuer import SessionIssuer
from crm_api.application.auth.setup_owner import (
    GetSetupStatusUseCase,
    SetupOwnerUseCase,
)
from crm_api.domain.auth.errors import SetupAlreadyCompletedError
from fakes import (
    FakeAuditEventRepository,
    FakePasswordHasher,
    FakeSessionRepository,
    FakeSessionTokenHasher,
    FakeTransaction,
    FakeUserRepository,
)


def _build_setup(
    users: FakeUserRepository,
) -> tuple[
    SetupOwnerUseCase,
    GetSetupStatusUseCase,
    FakeAuditEventRepository,
    FakeTransaction,
]:
    password_hasher = FakePasswordHasher()
    audit_events = FakeAuditEventRepository()
    transaction = FakeTransaction()
    session_issuer = SessionIssuer(
        sessions=FakeSessionRepository(),
        token_hasher=FakeSessionTokenHasher(),
        session_ttl=timedelta(hours=1),
    )
    return (
        SetupOwnerUseCase(
            users=users,
            password_hasher=password_hasher,
            session_issuer=session_issuer,
            audit=RecordAuditEventUseCase(events=audit_events),
            transaction=transaction,
        ),
        GetSetupStatusUseCase(users=users),
        audit_events,
        transaction,
    )


async def test_first_setup_creates_owner_and_issues_session() -> None:
    users = FakeUserRepository()
    setup, status, audit_events, transaction = _build_setup(users)

    assert await status.execute() is True

    result = await setup.execute(
        email="proprietario@deltaforce.internal",
        full_name="Proprietário Delta Force",
        password="correct-horse-battery-staple",
    )

    assert result.user.email == "proprietario@deltaforce.internal"
    assert result.session_token
    assert await status.execute() is False
    assert [event.action for event in audit_events.events] == ["auth.owner_setup"]
    assert transaction.commit_calls == 1


async def test_setup_is_rejected_after_owner_exists() -> None:
    users = FakeUserRepository()
    setup, _, audit_events, transaction = _build_setup(users)
    await setup.execute(
        email="proprietario@deltaforce.internal",
        full_name="Proprietário Delta Force",
        password="correct-horse-battery-staple",
    )

    with pytest.raises(SetupAlreadyCompletedError):
        await setup.execute(
            email="outro@deltaforce.internal",
            full_name="Outra pessoa",
            password="another-correct-password",
        )

    assert [event.action for event in audit_events.events] == [
        "auth.owner_setup",
        "auth.owner_setup",
    ]
    assert audit_events.events[-1].actor_user_id is None
    assert audit_events.events[-1].context == {"reason_code": "setup_already_completed"}
    assert transaction.commit_calls == 2
