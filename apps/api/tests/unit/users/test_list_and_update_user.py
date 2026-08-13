from uuid import uuid4

import pytest

from crm_api.application.users.list_users import ListUsersUseCase
from crm_api.application.users.update_user import UpdateUserUseCase
from crm_api.domain.users.errors import UserNotFoundError
from user_fakes import FakeUserRepository


async def test_list_users_returns_every_account() -> None:
    users = FakeUserRepository()
    await users.create(
        email="a@deltaforce.internal",
        full_name="A",
        password_hash="x",
        is_admin=False,
    )
    await users.create(
        email="b@deltaforce.internal",
        full_name="B",
        password_hash="x",
        is_admin=True,
    )

    result = await ListUsersUseCase(users=users).execute()

    assert {u.email for u in result} == {
        "a@deltaforce.internal",
        "b@deltaforce.internal",
    }


async def test_update_user_changes_only_given_fields() -> None:
    users = FakeUserRepository()
    user = await users.create(
        email="c@deltaforce.internal",
        full_name="Nome Antigo",
        password_hash="x",
        is_admin=False,
    )

    updated = await UpdateUserUseCase(users=users).execute(
        user_id=user.id, full_name="Nome Novo", is_admin=None
    )

    assert updated.full_name == "Nome Novo"
    assert updated.is_admin is False


async def test_update_unknown_user_raises() -> None:
    with pytest.raises(UserNotFoundError):
        await UpdateUserUseCase(users=FakeUserRepository()).execute(
            user_id=uuid4(), full_name="X", is_admin=None
        )
