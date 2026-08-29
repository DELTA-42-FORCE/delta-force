"""Confirma a configuração de conexão SQLite feita pelo adaptador (ADR 0003)."""

from pathlib import Path

import pytest

from crm_api.core.config import get_settings
from crm_api.infrastructure.database import get_engine


@pytest.fixture
async def sqlite_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_path = tmp_path / "pragma-check.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database_path}")
    get_settings.cache_clear()
    get_engine.cache_clear()
    engine = get_engine()
    try:
        yield engine
    finally:
        await engine.dispose()
        get_engine.cache_clear()
        get_settings.cache_clear()


async def test_sqlite_engine_enables_foreign_keys_wal_and_busy_timeout(
    sqlite_engine,
) -> None:
    async with sqlite_engine.connect() as connection:
        foreign_keys = (
            await connection.exec_driver_sql("PRAGMA foreign_keys")
        ).scalar()
        journal_mode = (
            await connection.exec_driver_sql("PRAGMA journal_mode")
        ).scalar()
        synchronous = (await connection.exec_driver_sql("PRAGMA synchronous")).scalar()
        busy_timeout = (
            await connection.exec_driver_sql("PRAGMA busy_timeout")
        ).scalar()

    assert foreign_keys == 1
    assert journal_mode.lower() == "wal"
    assert synchronous == 2  # FULL
    assert busy_timeout == 5000
