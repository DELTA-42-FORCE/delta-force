from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from crm_api.application.auth.get_current_user import GetCurrentUserUseCase
from crm_api.domain.auth.entities import Session, User
from crm_api.domain.auth.errors import InactiveUserError, InvalidSessionError
from fakes import FakeSessionRepository, FakeSessionTokenHasher, FakeUserRepository

ACTIVE_USER = User(
    id=uuid4(),
    email="ana@deltaforce.internal",
    full_name="Ana Interna",
    password_hash="irrelevant",
    is_active=True,
)

INACTIVE_USER = User(
    id=uuid4(),
    email="bruno@deltaforce.internal",
    full_name="Bruno Desligado",
    password_hash="irrelevant",
    is_active=False,
)


def _use_case_with(*, user: User, session: Session) -> GetCurrentUserUseCase:
    return GetCurrentUserUseCase(
        sessions=FakeSessionRepository({session.token_hash: session}),
        users=FakeUserRepository({user.email: user}),
        token_hasher=FakeSessionTokenHasher(),
    )


async def test_valid_session_resolves_the_owning_user() -> None:
    session = Session(
        token_hash="hashed:valid-token",
        user_id=ACTIVE_USER.id,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        revoked_at=None,
    )
    use_case = _use_case_with(user=ACTIVE_USER, session=session)

    resolved = await use_case.execute(session_token="valid-token")

    assert resolved.id == ACTIVE_USER.id


async def test_unknown_token_is_rejected() -> None:
    use_case = GetCurrentUserUseCase(
        sessions=FakeSessionRepository(),
        users=FakeUserRepository(),
        token_hasher=FakeSessionTokenHasher(),
    )

    with pytest.raises(InvalidSessionError):
        await use_case.execute(session_token="nonexistent-token")


async def test_expired_session_is_rejected() -> None:
    session = Session(
        token_hash="hashed:expired-token",
        user_id=ACTIVE_USER.id,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        revoked_at=None,
    )
    use_case = _use_case_with(user=ACTIVE_USER, session=session)

    with pytest.raises(InvalidSessionError):
        await use_case.execute(session_token="expired-token")


async def test_revoked_session_is_rejected() -> None:
    session = Session(
        token_hash="hashed:revoked-token",
        user_id=ACTIVE_USER.id,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        revoked_at=datetime.now(UTC),
    )
    use_case = _use_case_with(user=ACTIVE_USER, session=session)

    with pytest.raises(InvalidSessionError):
        await use_case.execute(session_token="revoked-token")


async def test_session_of_deactivated_user_is_rejected() -> None:
    session = Session(
        token_hash="hashed:valid-token",
        user_id=INACTIVE_USER.id,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        revoked_at=None,
    )
    use_case = _use_case_with(user=INACTIVE_USER, session=session)

    with pytest.raises(InactiveUserError):
        await use_case.execute(session_token="valid-token")
