from datetime import timedelta
from uuid import uuid4

import pytest

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.auth.authenticate_user import AuthenticateUserUseCase
from crm_api.application.auth.session_issuer import SessionIssuer
from crm_api.domain.audit.entities import AuditResult
from crm_api.domain.auth.entities import User
from crm_api.domain.auth.errors import InactiveUserError, InvalidCredentialsError
from fakes import (
    FakeAuditEventRepository,
    FakePasswordHasher,
    FakeSessionRepository,
    FakeSessionTokenHasher,
    FakeTransaction,
    FakeUserRepository,
)

ACTIVE_USER = User(
    id=uuid4(),
    email="ana@deltaforce.internal",
    full_name="Ana Interna",
    password_hash="correct-password",
    is_active=True,
)

INACTIVE_USER = User(
    id=uuid4(),
    email="bruno@deltaforce.internal",
    full_name="Bruno Desligado",
    password_hash="correct-password",
    is_active=False,
)


def _build_use_case(
    *users: User,
) -> tuple[AuthenticateUserUseCase, FakeAuditEventRepository, FakeTransaction]:
    audit_events = FakeAuditEventRepository()
    transaction = FakeTransaction()
    use_case = AuthenticateUserUseCase(
        users=FakeUserRepository({u.email: u for u in users}),
        password_hasher=FakePasswordHasher(),
        session_issuer=SessionIssuer(
            sessions=FakeSessionRepository(),
            token_hasher=FakeSessionTokenHasher(),
            session_ttl=timedelta(hours=1),
        ),
        audit=RecordAuditEventUseCase(events=audit_events),
        transaction=transaction,
    )
    return use_case, audit_events, transaction


async def test_login_with_correct_credentials_issues_a_session() -> None:
    use_case, audit_events, transaction = _build_use_case(ACTIVE_USER)

    result = await use_case.execute(
        email=ACTIVE_USER.email, password="correct-password"
    )

    assert result.user.id == ACTIVE_USER.id
    assert result.session.user_id == ACTIVE_USER.id
    assert result.session.revoked_at is None
    assert result.session.token_hash == f"hashed:{result.session_token}"
    assert [event.action for event in audit_events.events] == ["auth.login"]
    assert audit_events.events[0].result is AuditResult.SUCCESS
    assert transaction.commit_calls == 1
    assert transaction.rollback_calls == 0


async def test_login_with_wrong_password_is_rejected() -> None:
    use_case, audit_events, transaction = _build_use_case(ACTIVE_USER)

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(email=ACTIVE_USER.email, password="wrong-password")

    [event] = audit_events.events
    assert event.result is AuditResult.DENIED
    assert event.context == {"reason_code": "invalid_credentials"}
    assert ACTIVE_USER.email not in repr(event)
    assert "wrong-password" not in repr(event)
    assert transaction.commit_calls == 1


async def test_login_with_unknown_email_is_rejected() -> None:
    use_case, audit_events, _ = _build_use_case(ACTIVE_USER)

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(
            email="desconhecido@deltaforce.internal", password="correct-password"
        )

    [event] = audit_events.events
    assert event.context == {"reason_code": "invalid_credentials"}
    assert "desconhecido@deltaforce.internal" not in repr(event)


async def test_login_of_inactive_user_is_rejected() -> None:
    use_case, audit_events, _ = _build_use_case(INACTIVE_USER)

    with pytest.raises(InactiveUserError):
        await use_case.execute(email=INACTIVE_USER.email, password="correct-password")

    [event] = audit_events.events
    assert event.context == {"reason_code": "invalid_credentials"}
    assert event.actor_user_id is None
