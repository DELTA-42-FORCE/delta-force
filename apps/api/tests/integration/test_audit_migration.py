"""Prova de reversibilidade da fundação persistente de auditoria."""

import hashlib
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from psycopg.types.json import Json

from crm_api.core.config import get_settings
from crm_api.core.database_url_safety import ensure_loopback_database_url

pytestmark = pytest.mark.integration

API_DIRECTORY = Path(__file__).resolve().parents[2]
PREVIOUS_REVISION = "20260819_0003"


def run_alembic(command: str, revision: str) -> None:
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


def table_exists(
    connection: psycopg.Connection[tuple[object, ...]], table_name: str
) -> bool:
    result = connection.execute(
        "SELECT to_regclass(current_schema() || '.' || %s)",
        (table_name,),
    ).fetchone()
    assert result is not None
    return result[0] is not None


def ensure_disposable_database() -> None:
    url = get_settings().database_url
    if not url.startswith("postgresql+psycopg://"):
        pytest.skip("requires a postgresql+psycopg DATABASE_URL")
    ensure_loopback_database_url(url)
    with psycopg.connect(database_url()) as connection:
        result = connection.execute("SELECT current_database()").fetchone()
        assert result is not None
        database_name = str(result[0])
        if not database_name.startswith("delta_force_integration_"):
            message = "refusing audit migration test on non-disposable database"
            raise RuntimeError(f"{message}: {database_name!r}")


def test_audit_migration_round_trip_preserves_authentication_data() -> None:
    user_id = uuid.uuid4()
    token_hash = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    expires_at = datetime.now(UTC).replace(microsecond=0) + timedelta(days=1)

    ensure_disposable_database()
    try:
        with psycopg.connect(database_url()) as connection:
            assert table_exists(connection, "audit_events")
            connection.execute(
                """
                INSERT INTO users (id, email, full_name, password_hash)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    user_id,
                    f"audit-migration-{user_id}@deltaforce.internal",
                    "Synthetic Migration User",
                    "synthetic-password-hash",
                ),
            )
            connection.execute(
                """
                INSERT INTO sessions (token_hash, user_id, expires_at)
                VALUES (%s, %s, %s)
                """,
                (token_hash, user_id, expires_at),
            )

        run_alembic("downgrade", PREVIOUS_REVISION)
        with psycopg.connect(database_url()) as connection:
            assert not table_exists(connection, "audit_events")
            preserved_session = connection.execute(
                """
                SELECT user_id, expires_at
                FROM sessions
                WHERE token_hash = %s
                """,
                (token_hash,),
            ).fetchone()
            assert preserved_session == (user_id, expires_at)

        run_alembic("upgrade", "head")
        with psycopg.connect(database_url()) as connection:
            assert table_exists(connection, "audit_events")
            preserved_user = connection.execute(
                "SELECT id FROM users WHERE id = %s",
                (user_id,),
            ).fetchone()
            assert preserved_user == (user_id,)
            index_names = {
                str(row[0])
                for row in connection.execute(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = current_schema()
                      AND tablename = 'audit_events'
                    """
                ).fetchall()
            }
            assert {
                "ix_audit_events_actor_user_id",
                "ix_audit_events_occurred_at_id",
            } <= index_names
    finally:
        run_alembic("upgrade", "head")
        with psycopg.connect(database_url()) as connection:
            connection.execute(
                "DELETE FROM sessions WHERE token_hash = %s",
                (token_hash,),
            )
            connection.execute("DELETE FROM users WHERE id = %s", (user_id,))


def insert_audit_event(
    connection: psycopg.Connection[tuple[object, ...]],
    *,
    actor_kind: str,
    actor_user_id: uuid.UUID | None,
    action: str = "auth.login",
    resource_type: str = "owner_account",
    result: str = "success",
) -> uuid.UUID:
    event_id = uuid.uuid4()
    connection.execute(
        """
        INSERT INTO audit_events (
            id, actor_kind, actor_user_id, action, resource_type,
            resource_id, result, context
        )
        VALUES (%s, %s, %s, %s, %s, NULL, %s, %s)
        """,
        (
            event_id,
            actor_kind,
            actor_user_id,
            action,
            resource_type,
            result,
            Json({}),
        ),
    )
    return event_id


def test_audit_database_rejects_invalid_catalog_and_actor_identity() -> None:
    ensure_disposable_database()
    user_id = uuid.uuid4()
    event_id: uuid.UUID | None = None
    with psycopg.connect(database_url()) as connection:
        connection.execute(
            """
            INSERT INTO users (id, email, full_name, password_hash)
            VALUES (%s, %s, %s, %s)
            """,
            (
                user_id,
                f"audit-constraints-{user_id}@deltaforce.internal",
                "Synthetic Constraint User",
                "synthetic-password-hash",
            ),
        )

    rejected_cases: list[tuple[dict[str, object], type[psycopg.Error]]] = [
        (
            {
                "actor_kind": "anonymous",
                "actor_user_id": user_id,
            },
            psycopg.errors.CheckViolation,
        ),
        (
            {
                "actor_kind": "authenticated",
                "actor_user_id": uuid.uuid4(),
            },
            psycopg.errors.ForeignKeyViolation,
        ),
        (
            {
                "actor_kind": "anonymous",
                "actor_user_id": None,
                "result": "unknown",
            },
            psycopg.errors.CheckViolation,
        ),
        (
            {
                "actor_kind": "anonymous",
                "actor_user_id": None,
                "action": "person@example.com",
            },
            psycopg.errors.CheckViolation,
        ),
        (
            {
                "actor_kind": "anonymous",
                "actor_user_id": None,
                "resource_type": "raw-session-secret",
            },
            psycopg.errors.CheckViolation,
        ),
    ]

    try:
        for values, error_type in rejected_cases:
            with psycopg.connect(database_url()) as connection:
                with pytest.raises(error_type):
                    insert_audit_event(connection, **values)  # type: ignore[arg-type]

        with psycopg.connect(database_url()) as connection:
            event_id = insert_audit_event(
                connection,
                actor_kind="authenticated",
                actor_user_id=user_id,
            )

        with psycopg.connect(database_url()) as connection:
            with pytest.raises(psycopg.errors.ForeignKeyViolation):
                connection.execute("DELETE FROM users WHERE id = %s", (user_id,))
    finally:
        with psycopg.connect(database_url()) as connection:
            if event_id is not None:
                connection.execute(
                    "DELETE FROM audit_events WHERE id = %s", (event_id,)
                )
            connection.execute("DELETE FROM users WHERE id = %s", (user_id,))
