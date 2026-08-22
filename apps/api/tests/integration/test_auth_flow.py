import asyncio
import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text

from crm_api.domain.auth.entities import User
from crm_api.infrastructure.auth.models import SessionModel, UserModel
from crm_api.infrastructure.auth.passwords import BcryptPasswordHasher
from crm_api.infrastructure.auth.repositories import SqlAlchemyUserRepository
from crm_api.infrastructure.database import get_session_factory
from crm_api.main import app

pytestmark = pytest.mark.integration


async def test_concurrent_setup_creates_exactly_one_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with get_session_factory()() as session:
        database_name = await session.scalar(text("SELECT current_database()"))
        if database_name is None or not database_name.startswith(
            "delta_force_integration_"
        ):
            raise RuntimeError(
                f"refusing setup cleanup on non-disposable database {database_name!r}"
            )
        await session.execute(delete(SessionModel))
        await session.execute(delete(UserModel))
        await session.commit()

    original_create_owner = SqlAlchemyUserRepository.create_owner_if_none
    concurrent_requests = 0
    both_requests_arrived = asyncio.Event()

    async def synchronized_create_owner(
        repository: SqlAlchemyUserRepository,
        *,
        email: str,
        full_name: str,
        password_hash: str,
    ) -> User | None:
        nonlocal concurrent_requests
        concurrent_requests += 1
        if concurrent_requests == 2:
            both_requests_arrived.set()

        await asyncio.wait_for(both_requests_arrived.wait(), timeout=5)
        return await original_create_owner(
            repository,
            email=email,
            full_name=full_name,
            password_hash=password_hash,
        )

    monkeypatch.setattr(
        SqlAlchemyUserRepository,
        "create_owner_if_none",
        synchronized_create_owner,
    )
    payloads = (
        {
            "email": "first-owner@deltaforce.internal",
            "full_name": "Primeiro Proprietario",
            "password": "first-owner-password",
        },
        {
            "email": "second-owner@deltaforce.internal",
            "full_name": "Segundo Proprietario",
            "password": "second-owner-password",
        },
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        responses = await asyncio.gather(
            *(client.post("/auth/setup", json=payload) for payload in payloads)
        )

    assert sorted(response.status_code for response in responses) == [201, 409]
    created_response = next(
        response for response in responses if response.status_code == 201
    )

    async with get_session_factory()() as session:
        owners = (await session.scalars(select(UserModel))).all()

    assert len(owners) == 1
    assert owners[0].email == created_response.json()["user"]["email"]


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

    async with get_session_factory()() as session:
        stored_session = await session.get(
            SessionModel, hashlib.sha256(token.encode("utf-8")).hexdigest()
        )
        assert stored_session is not None
        assert stored_session.token_hash != token

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
