from collections.abc import Iterator
from datetime import timedelta
from typing import Annotated
from uuid import uuid4

import pytest
from fastapi import Depends, HTTPException, status
from fastapi.testclient import TestClient

from crm_api.application.auth.authenticate_user import AuthenticateUserUseCase
from crm_api.application.auth.get_current_user import GetCurrentUserUseCase
from crm_api.application.auth.logout import LogoutUseCase
from crm_api.application.auth.setup_owner import (
    GetSetupStatusUseCase,
    SetupOwnerUseCase,
)
from crm_api.domain.auth.entities import User
from crm_api.domain.auth.errors import InactiveUserError, InvalidSessionError
from crm_api.main import app
from crm_api.presentation.auth import dependencies
from fakes import (
    FakePasswordHasher,
    FakeSessionRepository,
    FakeSessionTokenHasher,
    FakeUserRepository,
)

ACTIVE_USER = User(
    id=uuid4(),
    email="ana@deltaforce.internal",
    full_name="Ana Interna",
    password_hash="correct-password",
    is_active=True,
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    users = FakeUserRepository({ACTIVE_USER.email: ACTIVE_USER})
    sessions = FakeSessionRepository()

    async def override_get_current_user(
        session_token: Annotated[str, Depends(dependencies.get_bearer_token)],
    ) -> User:
        try:
            return await GetCurrentUserUseCase(
                sessions=sessions,
                users=users,
                token_hasher=FakeSessionTokenHasher(),
            ).execute(session_token=session_token)
        except (InvalidSessionError, InactiveUserError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid or expired session",
            ) from None

    def override_authenticate_use_case() -> AuthenticateUserUseCase:
        return AuthenticateUserUseCase(
            users=users,
            sessions=sessions,
            password_hasher=FakePasswordHasher(),
            token_hasher=FakeSessionTokenHasher(),
            session_ttl=timedelta(hours=1),
        )

    def override_logout_use_case() -> LogoutUseCase:
        return LogoutUseCase(sessions=sessions, token_hasher=FakeSessionTokenHasher())

    app.dependency_overrides[dependencies.get_authenticate_user_use_case] = (
        override_authenticate_use_case
    )
    app.dependency_overrides[dependencies.get_logout_use_case] = (
        override_logout_use_case
    )
    app.dependency_overrides[dependencies.get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_login_with_valid_credentials_returns_a_session_token(
    client: TestClient,
) -> None:
    response = client.post(
        "/auth/login",
        json={"email": ACTIVE_USER.email, "password": "correct-password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == ACTIVE_USER.email
    assert body["session_token"]


def test_login_with_wrong_password_returns_401(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"email": ACTIVE_USER.email, "password": "wrong-password"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/auth/setup",
            {
                "email": "proprietario@deltaforce.internal",
                "full_name": "Proprietário Delta Force",
                "password": "á" * 37,
            },
        ),
        (
            "/auth/login",
            {"email": ACTIVE_USER.email, "password": "á" * 37},
        ),
    ],
)
def test_auth_routes_reject_password_over_72_utf8_bytes(
    client: TestClient, path: str, payload: dict[str, str]
) -> None:
    response = client.post(path, json=payload)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "password"]


def test_protected_route_without_token_is_rejected(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_protected_route_with_invalid_token_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 401


def test_full_login_then_me_then_logout_cycle(client: TestClient) -> None:
    login_response = client.post(
        "/auth/login",
        json={"email": ACTIVE_USER.email, "password": "correct-password"},
    )
    token = login_response.json()["session_token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    me_response = client.get("/auth/me", headers=auth_header)
    assert me_response.status_code == 200
    assert me_response.json()["email"] == ACTIVE_USER.email

    logout_response = client.post("/auth/logout", headers=auth_header)
    assert logout_response.status_code == 204

    me_after_logout = client.get("/auth/me", headers=auth_header)
    assert me_after_logout.status_code == 401


def test_first_setup_creates_owner_and_returns_session() -> None:
    users = FakeUserRepository()
    sessions = FakeSessionRepository()
    password_hasher = FakePasswordHasher()
    authenticate = AuthenticateUserUseCase(
        users=users,
        sessions=sessions,
        password_hasher=password_hasher,
        token_hasher=FakeSessionTokenHasher(),
        session_ttl=timedelta(hours=1),
    )
    setup = SetupOwnerUseCase(
        users=users,
        password_hasher=password_hasher,
        authenticate=authenticate,
    )
    app.dependency_overrides[dependencies.get_setup_status_use_case] = lambda: (
        GetSetupStatusUseCase(users=users)
    )
    app.dependency_overrides[dependencies.get_setup_owner_use_case] = lambda: setup

    try:
        with TestClient(app) as setup_client:
            status_response = setup_client.get("/auth/setup")
            assert status_response.json() == {"requires_setup": True}

            response = setup_client.post(
                "/auth/setup",
                json={
                    "email": "proprietario@deltaforce.internal",
                    "full_name": "Proprietário Delta Force",
                    "password": "correct-horse-battery-staple",
                },
            )
            assert response.status_code == 201
            assert response.json()["session_token"]
            assert setup_client.get("/auth/setup").json() == {"requires_setup": False}

            duplicate = setup_client.post(
                "/auth/setup",
                json={
                    "email": "outra@deltaforce.internal",
                    "full_name": "Outra pessoa",
                    "password": "another-correct-password",
                },
            )
            assert duplicate.status_code == 409
    finally:
        app.dependency_overrides.clear()
