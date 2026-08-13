import uuid

import pytest
from fastapi.testclient import TestClient

from crm_api.infrastructure.auth.models import UserModel
from crm_api.infrastructure.auth.passwords import BcryptPasswordHasher
from crm_api.infrastructure.database import get_session_factory
from crm_api.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
async def internal_user() -> tuple[str, str]:
    email = f"integration-{uuid.uuid4()}@deltaforce.internal"
    password = "correct-horse-battery-staple"

    async with get_session_factory()() as session:
        session.add(
            UserModel(
                id=uuid.uuid4(),
                email=email,
                full_name="Usuário de Integração",
                password_hash=BcryptPasswordHasher().hash(password),
                is_active=True,
            )
        )
        await session.commit()

    return email, password


async def test_authenticated_user_can_reach_a_protected_route_and_logout(
    internal_user: tuple[str, str],
) -> None:
    email, password = internal_user
    client = TestClient(app)

    login_response = client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert login_response.status_code == 200
    token = login_response.json()["session_token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    me_response = client.get("/auth/me", headers=auth_header)
    assert me_response.status_code == 200
    assert me_response.json()["email"] == email

    logout_response = client.post("/auth/logout", headers=auth_header)
    assert logout_response.status_code == 204

    rejected_response = client.get("/auth/me", headers=auth_header)
    assert rejected_response.status_code == 401


async def test_wrong_password_is_rejected_without_creating_a_session(
    internal_user: tuple[str, str],
) -> None:
    email, _ = internal_user
    client = TestClient(app)

    response = client.post(
        "/auth/login", json={"email": email, "password": "wrong-password"}
    )

    assert response.status_code == 401
