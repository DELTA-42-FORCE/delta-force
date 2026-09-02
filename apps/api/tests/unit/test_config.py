from pathlib import Path

import pytest
from pydantic import ValidationError

from crm_api.core.config import get_settings


def test_settings_accepts_sqlite_aiosqlite_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./crm.sqlite3")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url.endswith("/crm.sqlite3")
    get_settings.cache_clear()


def test_settings_accepts_async_psycopg_url_during_transition(
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

    with pytest.raises(ValidationError, match="sqlite\\+aiosqlite"):
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


def test_documents_root_defaults_to_a_directory_next_to_the_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    database_path = tmp_path / "dados" / "crm.sqlite3"
    monkeypatch.delenv("DOCUMENTS_ROOT", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", f"sqlite+aiosqlite:///{database_path.as_posix()}"
    )
    get_settings.cache_clear()

    # Banco e documentos na mesma árvore para o backup conjunto da #44.
    expected = database_path.resolve().parent / "documents"
    assert get_settings().documents_root_path == expected
    get_settings.cache_clear()


def test_documents_root_accepts_an_explicit_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    override = tmp_path / "acervo"
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./crm.sqlite3")
    monkeypatch.setenv("DOCUMENTS_ROOT", str(override))
    get_settings.cache_clear()

    assert get_settings().documents_root_path == override.resolve()
    get_settings.cache_clear()


def test_documents_root_requires_configuration_without_a_local_database_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DOCUMENTS_ROOT", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://user:password@localhost:5432/crm"
    )
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="DOCUMENTS_ROOT is required"):
        get_settings().documents_root_path

    get_settings.cache_clear()
