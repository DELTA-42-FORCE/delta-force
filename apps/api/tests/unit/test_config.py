import pytest
from pydantic import ValidationError

from crm_api.core.config import get_settings


def test_settings_accepts_async_psycopg_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:password@localhost:5432/crm",
    )
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url.endswith("/crm")
    get_settings.cache_clear()


def test_settings_rejects_a_non_standard_database_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:5432/crm")
    get_settings.cache_clear()

    with pytest.raises(ValidationError, match="postgresql\\+psycopg"):
        get_settings()

    get_settings.cache_clear()


def test_cors_allowed_origins_list_splits_on_comma(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://user:password@localhost:5432/crm"
    )
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS", "http://localhost:5173, http://localhost:4173"
    )
    get_settings.cache_clear()

    assert get_settings().cors_allowed_origins_list == [
        "http://localhost:5173",
        "http://localhost:4173",
    ]
    get_settings.cache_clear()
