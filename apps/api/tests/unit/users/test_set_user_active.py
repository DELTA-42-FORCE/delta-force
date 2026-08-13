from uuid import uuid4

import pytest

from crm_api.application.users.set_user_active import SetUserActiveUseCase
from crm_api.domain.users.errors import CannotDeactivateSelfError, UserNotFoundError
from user_fakes import FakeUserRepository


async def test_admin_can_deactivate_another_user() -> None:
    users = FakeUserRepository()
    admin = await users.create(
        email="admin@deltaforce.internal",
        full_name="Admin",
        password_hash="x",
        is_admin=True,
    )
    target = await users.create(
        email="user@deltaforce.internal",
        full_name="User",
        password_hash="x",
        is_admin=False,
    )

    updated = await SetUserActiveUseCase(users=users).execute(
        acting_admin_id=admin.id, user_id=target.id, is_active=False
    )

    assert updated.is_active is False


async def test_admin_cannot_deactivate_self() -> None:
    users = FakeUserRepository()
    admin = await users.create(
        email="admin@deltaforce.internal",
        full_name="Admin",
        password_hash="x",
        is_admin=True,
    )

    with pytest.raises(CannotDeactivateSelfError):
        await SetUserActiveUseCase(users=users).execute(
            acting_admin_id=admin.id, user_id=admin.id, is_active=False
        )


async def test_activating_unknown_user_raises() -> None:
    with pytest.raises(UserNotFoundError):
        await SetUserActiveUseCase(users=FakeUserRepository()).execute(
            acting_admin_id=uuid4(), user_id=uuid4(), is_active=True
        )
