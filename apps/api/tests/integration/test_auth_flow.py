import asyncio
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text

from crm_api.domain.auth.entities import User
from crm_api.infrastructure.audit.models import AuditEventModel
from crm_api.infrastructure.audit.repositories import (
    SqlAlchemyAuditEventRepository,
)
from crm_api.infrastructure.auth.models import SessionModel, UserModel
from crm_api.infrastructure.auth.passwords import BcryptPasswordHasher
from crm_api.infrastructure.auth.repositories import SqlAlchemyUserRepository
from crm_api.infrastructure.database import get_session_factory
from crm_api.main import app

pytestmark = pytest.mark.integration


async def clear_disposable_auth_data() -> None:
    async with get_session_factory()() as session:
        database_name = await session.scalar(text("SELECT current_database()"))
        if database_name is None or not database_name.startswith(
            "delta_force_integration_"
        ):
            raise RuntimeError(
                "refusing auth cleanup on non-disposable database " f"{database_name!r}"
            )
        await session.execute(delete(AuditEventModel))
        await session.execute(delete(SessionModel))
        await session.execute(delete(UserModel))
        await session.commit()


async def audit_event_ids() -> set[uuid.UUID]:
    async with get_session_factory()() as session:
        return set(await session.scalars(select(AuditEventModel.id)))


async def audit_events_created_after(
    existing_ids: set[uuid.UUID],
) -> list[AuditEventModel]:
    async with get_session_factory()() as session:
        events = (await session.scalars(select(AuditEventModel))).all()
    return [event for event in events if event.id not in existing_ids]


async def test_concurrent_setup_creates_exactly_one_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await clear_disposable_auth_data()

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
        setup_events = (
            await session.scalars(
                select(AuditEventModel).where(
                    AuditEventModel.action == "auth.owner_setup"
                )
            )
        ).all()

    assert len(owners) == 1
    assert owners[0].email == created_response.json()["user"]["email"]
    assert sorted(event.result for event in setup_events) == ["denied", "success"]
    assert len(setup_events) == 2
    success_event = next(event for event in setup_events if event.result == "success")
    denied_event = next(event for event in setup_events if event.result == "denied")
    assert success_event.actor_user_id == owners[0].id
    assert success_event.resource_id == str(owners[0].id)
    assert denied_event.actor_user_id is None
    assert denied_event.context == {"reason_code": "setup_already_completed"}


async def test_audit_failure_rolls_back_owner_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await clear_disposable_auth_data()

    async def fail_to_append(
        repository: SqlAlchemyAuditEventRepository,
        event: object,
    ) -> None:
        raise RuntimeError("synthetic audit persistence failure")

    monkeypatch.setattr(
        SqlAlchemyAuditEventRepository,
        "append",
        fail_to_append,
    )

    with pytest.raises(RuntimeError, match="synthetic audit persistence failure"):
        with TestClient(app) as client:
            client.post(
                "/auth/setup",
                json={
                    "email": "rollback-owner@deltaforce.internal",
                    "full_name": "Synthetic Rollback Owner",
                    "password": "correct-horse-battery-staple",
                },
            )

    async with get_session_factory()() as session:
        owners = (await session.scalars(select(UserModel))).all()
        sessions = (await session.scalars(select(SessionModel))).all()
        events = (await session.scalars(select(AuditEventModel))).all()

    assert owners == []
    assert sessions == []
    assert events == []


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
    existing_event_ids = await audit_event_ids()

    response = client.post(
        "/auth/login", json={"email": email, "password": "wrong-password"}
    )

    assert response.status_code == 401
    [event] = await audit_events_created_after(existing_event_ids)
    assert event.action == "auth.login"
    assert event.result == "denied"
    assert event.actor_user_id is None
    assert event.context == {"reason_code": "invalid_credentials"}
    serialized_event = str(
        (event.action, event.resource_type, event.resource_id, event.context)
    )
    assert email not in serialized_event
    assert "wrong-password" not in serialized_event


async def test_inactive_user_session_is_denied_and_audited(
    internal_user: tuple[str, str],
) -> None:
    email, password = internal_user
    client = TestClient(app)
    login_response = client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert login_response.status_code == 200
    token = login_response.json()["session_token"]

    async with get_session_factory()() as session:
        user = await session.scalar(select(UserModel).where(UserModel.email == email))
        assert user is not None
        user.is_active = False
        await session.commit()

    existing_event_ids = await audit_event_ids()
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    [event] = await audit_events_created_after(existing_event_ids)
    assert event.action == "auth.access_denied"
    assert event.result == "denied"
    assert event.actor_user_id is None
    assert event.context == {
        "route_template": "/auth/me",
        "http_method": "GET",
        "reason_code": "invalid_session",
    }
    assert email not in str(event.context)
    assert token not in str(event.context)


async def test_authentication_actions_are_audited_without_secrets(
    internal_user: tuple[str, str],
) -> None:
    email, password = internal_user
    client = TestClient(app)
    raw_invalid_token = "synthetic-invalid-session-token"
    raw_expired_token = "synthetic-expired-session-token"

    missing_response = client.get("/audit/events")
    assert missing_response.status_code == 401

    invalid_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {raw_invalid_token}"},
    )
    assert invalid_response.status_code == 401

    login_response = client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert login_response.status_code == 200
    owner_id = uuid.UUID(login_response.json()["user"]["id"])
    token = login_response.json()["session_token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    me_response = client.get("/auth/me", headers=auth_header)
    assert me_response.status_code == 200

    audit_response = client.get(
        "/audit/events",
        headers=auth_header,
        params={"limit": 1},
    )
    assert audit_response.status_code == 200
    first_page = audit_response.json()
    assert first_page["items"][0]["action"] == "auth.owner_profile_view"
    cursor = first_page["next_cursor"]
    assert cursor is not None

    second_page_response = client.get(
        "/audit/events",
        headers=auth_header,
        params={
            "limit": 1,
            "before_occurred_at": cursor["occurred_at"],
            "before_id": cursor["id"],
        },
    )
    assert second_page_response.status_code == 200
    second_page = second_page_response.json()
    assert second_page["items"][0]["action"] == "auth.login"
    assert second_page["items"][0]["id"] != first_page["items"][0]["id"]

    filtered_response = client.get(
        "/audit/events",
        headers=auth_header,
        params={"action": "auth.login", "result": "success"},
    )
    assert filtered_response.status_code == 200
    filtered_items = filtered_response.json()["items"]
    assert len(filtered_items) == 1
    assert filtered_items[0]["action"] == "auth.login"
    assert filtered_items[0]["result"] == "success"

    logout_response = client.post("/auth/logout", headers=auth_header)
    assert logout_response.status_code == 204
    revoked_response = client.get("/auth/me", headers=auth_header)
    assert revoked_response.status_code == 401

    async with get_session_factory()() as session:
        session.add(
            SessionModel(
                token_hash=hashlib.sha256(
                    raw_expired_token.encode("utf-8")
                ).hexdigest(),
                user_id=owner_id,
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        await session.commit()

    expired_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {raw_expired_token}"},
    )
    assert expired_response.status_code == 401

    async with get_session_factory()() as session:
        events = (
            await session.scalars(
                select(AuditEventModel).order_by(
                    AuditEventModel.occurred_at,
                    AuditEventModel.id,
                )
            )
        ).all()

    owner_actions = [
        event.action for event in events if event.actor_user_id == owner_id
    ]
    assert owner_actions == [
        "auth.login",
        "auth.owner_profile_view",
        "audit.log_view",
        "audit.log_view",
        "audit.log_view",
        "auth.logout",
    ]
    denied_events = [
        event
        for event in events
        if event.action == "auth.access_denied" and event.result == "denied"
    ]
    denied_routes = [event.context["route_template"] for event in denied_events]
    assert "/audit/events" in denied_routes
    assert denied_routes.count("/auth/me") >= 3
    assert all(
        event.context["reason_code"] == "invalid_session" for event in denied_events
    )

    serialized_response = (
        audit_response.text + second_page_response.text + filtered_response.text
    ).lower()
    serialized_events = str(
        [
            (
                event.action,
                event.resource_type,
                event.resource_id,
                event.context,
            )
            for event in events
        ]
    ).lower()
    for sensitive_value in (
        email,
        password,
        token,
        hashlib.sha256(token.encode("utf-8")).hexdigest(),
        raw_invalid_token,
        raw_expired_token,
    ):
        assert sensitive_value.lower() not in serialized_response
        assert sensitive_value.lower() not in serialized_events


async def test_audit_failure_rolls_back_session_creation(
    internal_user: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email, password = internal_user

    async def fail_to_append(
        repository: SqlAlchemyAuditEventRepository,
        event: object,
    ) -> None:
        raise RuntimeError("synthetic audit persistence failure")

    monkeypatch.setattr(
        SqlAlchemyAuditEventRepository,
        "append",
        fail_to_append,
    )

    with pytest.raises(RuntimeError, match="synthetic audit persistence failure"):
        TestClient(app).post(
            "/auth/login",
            json={"email": email, "password": password},
        )

    async with get_session_factory()() as session:
        user_id = await session.scalar(
            select(UserModel.id).where(UserModel.email == email)
        )
        sessions = (
            await session.scalars(
                select(SessionModel).where(SessionModel.user_id == user_id)
            )
        ).all()

    assert sessions == []


async def test_audit_failure_rolls_back_logout_revocation(
    internal_user: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email, password = internal_user
    with TestClient(app) as client:
        login_response = client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        assert login_response.status_code == 200
        token = login_response.json()["session_token"]
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        async def fail_to_append(
            repository: SqlAlchemyAuditEventRepository,
            event: object,
        ) -> None:
            raise RuntimeError("synthetic audit persistence failure")

        monkeypatch.setattr(
            SqlAlchemyAuditEventRepository,
            "append",
            fail_to_append,
        )

        with pytest.raises(
            RuntimeError,
            match="synthetic audit persistence failure",
        ):
            client.post(
                "/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
            )

    async with get_session_factory()() as session:
        stored_session = await session.get(SessionModel, token_hash)

    assert stored_session is not None
    assert stored_session.revoked_at is None
