"""Regressão do ciclo reversível da migration de tokens de sessão."""

import hashlib
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest

from crm_api.core.config import get_settings
from crm_api.core.database_url_safety import ensure_loopback_database_url

pytestmark = pytest.mark.integration

API_DIRECTORY = Path(__file__).resolve().parents[2]
LEGACY_REVISION = "20260812_0002"


def run_alembic(command: str, revision: str) -> None:
    """Executa uma transição isolada com a mesma configuração da aplicação."""
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(API_DIRECTORY / "alembic.ini"),
            command,
            revision,
        ],
        cwd=API_DIRECTORY,
        check=True,
    )


def database_url() -> str:
    return get_settings().database_url.replace(
        "postgresql+psycopg://", "postgresql://", 1
    )


def primary_key_name(connection: psycopg.Connection[tuple[object, ...]]) -> str:
    result = connection.execute(
        """
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_schema = current_schema()
          AND table_name = 'sessions'
          AND constraint_type = 'PRIMARY KEY'
        """
    ).fetchone()
    assert result is not None
    return str(result[0])


def ensure_disposable_database() -> None:
    url = get_settings().database_url
    ensure_loopback_database_url(url)
    with psycopg.connect(database_url()) as connection:
        result = connection.execute("SELECT current_database()").fetchone()
        assert result is not None
        database_name = str(result[0])
        if not database_name.startswith("delta_force_integration_"):
            message = "refusing migration round trip on non-disposable database"
            raise RuntimeError(f"{message}: {database_name!r}")


def test_session_token_migration_survives_round_trip() -> None:
    user_id = uuid.uuid4()
    raw_token = f"migration-roundtrip-{uuid.uuid4().hex}"
    first_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    second_hash = hashlib.sha256(first_hash.encode("utf-8")).hexdigest()
    expires_at = datetime.now(UTC).replace(microsecond=0) + timedelta(days=1)
    revoked_at = expires_at - timedelta(hours=1)

    ensure_disposable_database()
    run_alembic("downgrade", LEGACY_REVISION)
    try:
        with psycopg.connect(database_url()) as connection:
            assert primary_key_name(connection) == "sessions_pkey"
            connection.execute(
                """
                INSERT INTO users (id, email, full_name, password_hash)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    user_id,
                    f"migration-{user_id}@deltaforce.internal",
                    "Usuário de Migração",
                    "synthetic-password-hash",
                ),
            )
            connection.execute(
                """
                INSERT INTO sessions (token, user_id, expires_at, revoked_at)
                VALUES (%s, %s, %s, %s)
                """,
                (raw_token, user_id, expires_at, revoked_at),
            )

        run_alembic("upgrade", "head")
        with psycopg.connect(database_url()) as connection:
            assert primary_key_name(connection) == "pk_sessions"
            upgraded = connection.execute(
                """
                SELECT token_hash, user_id, expires_at, revoked_at
                FROM sessions
                WHERE user_id = %s
                """,
                (user_id,),
            ).fetchone()
            assert upgraded == (first_hash, user_id, expires_at, revoked_at)

        run_alembic("downgrade", LEGACY_REVISION)
        with psycopg.connect(database_url()) as connection:
            assert primary_key_name(connection) == "sessions_pkey"
            downgraded = connection.execute(
                """
                SELECT token, user_id, expires_at, revoked_at
                FROM sessions
                WHERE user_id = %s
                """,
                (user_id,),
            ).fetchone()
            assert downgraded == (first_hash, user_id, expires_at, revoked_at)

        run_alembic("upgrade", "head")
        with psycopg.connect(database_url()) as connection:
            assert primary_key_name(connection) == "pk_sessions"
            upgraded_again = connection.execute(
                """
                SELECT token_hash, user_id, expires_at, revoked_at
                FROM sessions
                WHERE user_id = %s
                """,
                (user_id,),
            ).fetchone()
            assert upgraded_again == (second_hash, user_id, expires_at, revoked_at)
    finally:
        run_alembic("upgrade", "head")
        with psycopg.connect(database_url()) as connection:
            connection.execute("DELETE FROM users WHERE id = %s", (user_id,))
