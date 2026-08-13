from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from crm_api.application.users.create_user import CreateUserUseCase
from crm_api.application.users.list_users import ListUsersUseCase
from crm_api.application.users.set_user_active import SetUserActiveUseCase
from crm_api.application.users.update_user import UpdateUserUseCase
from crm_api.domain.auth.entities import User
from crm_api.main import app
from crm_api.presentation.auth import dependencies as auth_dependencies
from crm_api.presentation.users import dependencies as users_dependencies
from user_fakes import FakePasswordHasher, FakeUserRepository

ADMIN_USER = User(
    id=uuid4(),
    email="admin@deltaforce.internal",
    full_name="Admin",
    password_hash="x",
    is_active=True,
    is_admin=True,
)

REGULAR_USER = User(
    id=uuid4(),
    email="regular@deltaforce.internal",
    full_name="Regular",
    password_hash="x",
    is_active=True,
    is_admin=False,
)


def _client_as(current_user: User) -> Iterator[TestClient]:
    users = FakeUserRepository({current_user.id: current_user})

    async def override_get_current_user() -> User:
        return current_user

    app.dependency_overrides[auth_dependencies.get_current_user] = (
        override_get_current_user
    )
    app.dependency_overrides[users_dependencies.get_create_user_use_case] = (
        lambda: CreateUserUseCase(users=users, password_hasher=FakePasswordHasher())
    )
    app.dependency_overrides[users_dependencies.get_list_users_use_case] = (
        lambda: ListUsersUseCase(users=users)
    )
    app.dependency_overrides[users_dependencies.get_update_user_use_case] = (
        lambda: UpdateUserUseCase(users=users)
    )
    app.dependency_overrides[users_dependencies.get_set_user_active_use_case] = (
        lambda: SetUserActiveUseCase(users=users)
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def admin_client() -> Iterator[TestClient]:
    yield from _client_as(ADMIN_USER)


@pytest.fixture
def regular_client() -> Iterator[TestClient]:
    yield from _client_as(REGULAR_USER)


def test_admin_can_create_and_list_users(admin_client: TestClient) -> None:
    create_response = admin_client.post(
        "/users",
        json={
            "email": "nova@deltaforce.internal",
            "full_name": "Nova Conta",
            "password": "senha-forte-123",
        },
    )
    assert create_response.status_code == 201

    list_response = admin_client.get("/users")
    assert list_response.status_code == 200
    emails = {user["email"] for user in list_response.json()}
    assert "nova@deltaforce.internal" in emails


def test_regular_user_cannot_manage_users(regular_client: TestClient) -> None:
    response = regular_client.get("/users")

    assert response.status_code == 403


def test_admin_can_deactivate_and_reactivate_a_user(admin_client: TestClient) -> None:
    create_response = admin_client.post(
        "/users",
        json={
            "email": "alvo@deltaforce.internal",
            "full_name": "Alvo",
            "password": "senha-forte-123",
        },
    )
    user_id = create_response.json()["id"]

    deactivate_response = admin_client.post(f"/users/{user_id}/deactivate")
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False

    activate_response = admin_client.post(f"/users/{user_id}/activate")
    assert activate_response.status_code == 200
    assert activate_response.json()["is_active"] is True


def test_admin_cannot_deactivate_self(admin_client: TestClient) -> None:
    response = admin_client.post(f"/users/{ADMIN_USER.id}/deactivate")

    assert response.status_code == 409
