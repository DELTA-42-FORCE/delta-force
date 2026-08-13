from datetime import timedelta
from uuid import uuid4

import pytest

from crm_api.application.auth.authenticate_user import AuthenticateUserUseCase
from crm_api.domain.auth.entities import User
from crm_api.domain.auth.errors import InactiveUserError, InvalidCredentialsError
from fakes import FakePasswordHasher, FakeSessionRepository, FakeUserRepository

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


def _build_use_case(*users: User) -> AuthenticateUserUseCase:
    return AuthenticateUserUseCase(
        users=FakeUserRepository({u.email: u for u in users}),
        sessions=FakeSessionRepository(),
        password_hasher=FakePasswordHasher(),
        session_ttl=timedelta(hours=1),
    )


async def test_login_with_correct_credentials_issues_a_session() -> None:
    use_case = _build_use_case(ACTIVE_USER)

    result = await use_case.execute(
        email=ACTIVE_USER.email, password="correct-password"
    )

    assert result.user.id == ACTIVE_USER.id
    assert result.session.user_id == ACTIVE_USER.id
    assert result.session.revoked_at is None


async def test_login_with_wrong_password_is_rejected() -> None:
    use_case = _build_use_case(ACTIVE_USER)

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(email=ACTIVE_USER.email, password="wrong-password")


async def test_login_with_unknown_email_is_rejected() -> None:
    use_case = _build_use_case(ACTIVE_USER)

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(
            email="desconhecido@deltaforce.internal", password="correct-password"
        )


async def test_login_of_inactive_user_is_rejected() -> None:
    use_case = _build_use_case(INACTIVE_USER)

    with pytest.raises(InactiveUserError):
        await use_case.execute(email=INACTIVE_USER.email, password="correct-password")
