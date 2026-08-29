import pytest
from fastapi.testclient import TestClient

from crm_api.main import app

pytestmark = pytest.mark.integration


def test_readiness_check_connects_to_the_configured_database() -> None:
    response = TestClient(app).get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
