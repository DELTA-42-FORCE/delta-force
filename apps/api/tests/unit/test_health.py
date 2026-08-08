from fastapi.testclient import TestClient

from crm_api.main import app


def test_health_check_returns_ok() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
