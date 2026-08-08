import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from crm_api import main


def test_health_check_returns_ok() -> None:
    response = TestClient(main.app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_check_returns_ok_when_database_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def connection_is_available() -> None:
        return None

    monkeypatch.setattr(main, "check_database_connection", connection_is_available)

    response = TestClient(main.app).get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_readiness_check_hides_database_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def connection_is_unavailable() -> None:
        raise SQLAlchemyError("connection details must not be exposed")

    monkeypatch.setattr(main, "check_database_connection", connection_is_unavailable)

    response = TestClient(main.app).get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
