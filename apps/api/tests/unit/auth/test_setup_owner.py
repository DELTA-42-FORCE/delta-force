from datetime import timedelta

import pytest

from crm_api.application.auth.authenticate_user import AuthenticateUserUseCase
from crm_api.application.auth.setup_owner import (
    GetSetupStatusUseCase,
    SetupOwnerUseCase,
)
from crm_api.domain.auth.errors import SetupAlreadyCompletedError
from fakes import (
    FakePasswordHasher,
    FakeSessionRepository,
    FakeSessionTokenHasher,
    FakeUserRepository,
)


def _build_setup(
    users: FakeUserRepository,
) -> tuple[SetupOwnerUseCase, GetSetupStatusUseCase]:
    password_hasher = FakePasswordHasher()
    authenticate = AuthenticateUserUseCase(
        users=users,
        sessions=FakeSessionRepository(),
        password_hasher=password_hasher,
        token_hasher=FakeSessionTokenHasher(),
        session_ttl=timedelta(hours=1),
    )
    return (
        SetupOwnerUseCase(
            users=users,
            password_hasher=password_hasher,
            authenticate=authenticate,
        ),
        GetSetupStatusUseCase(users=users),
    )


async def test_first_setup_creates_owner_and_issues_session() -> None:
    users = FakeUserRepository()
    setup, status = _build_setup(users)

    assert await status.execute() is True

    result = await setup.execute(
        email="proprietario@deltaforce.internal",
        full_name="Proprietário Delta Force",
        password="correct-horse-battery-staple",
    )

    assert result.user.email == "proprietario@deltaforce.internal"
    assert result.session_token
    assert await status.execute() is False


async def test_setup_is_rejected_after_owner_exists() -> None:
    users = FakeUserRepository()
    setup, _ = _build_setup(users)
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
