"""Prova de portabilidade SQLite dos ciclos de migration (ADR 0003 / #54).

Espelha os testes de migration em test_session_token_migration.py e
test_audit_migration.py, mas usando o driver sqlite3 da biblioteca padrão
sobre o arquivo descartável criado por scripts/run_sqlite_integration_tests.py,
em vez de psycopg contra o PostgreSQL local.
"""

import hashlib
import sqlite3
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from crm_api.core.config import get_settings

pytestmark = pytest.mark.integration

API_DIRECTORY = Path(__file__).resolve().parents[2]
LEGACY_SESSION_REVISION = "20260812_0002"
PREVIOUS_AUDIT_REVISION = "20260819_0003"
PREVIOUS_CLIENT_FOLDER_REVISION = "20260829_0005"
PREVIOUS_VIEW_UPDATE_REVISION = "20260830_0006"
PREVIOUS_DOCUMENT_REVISION = "20260901_0007"
PREVIOUS_ANNOTATION_REVISION = "20260902_0008"
PREVIOUS_DOCUMENT_STATUS_REVISION = "20260903_0010"


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


def ensure_disposable_database() -> Path:
    """Confirma que os testes só operam sobre o arquivo SQLite descartável."""
    url = get_settings().database_url
    prefix = "sqlite+aiosqlite:///"
    if not url.startswith(prefix):
        pytest.skip("requires a sqlite+aiosqlite DATABASE_URL")

    path = Path(url.removeprefix(prefix))
    if not path.stem.startswith("delta_force_integration_"):
        message = "refusing sqlite migration test on non-disposable database"
        raise RuntimeError(f"{message}: {path!r}")
    return path


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table_name})")}


def test_session_token_migration_survives_round_trip() -> None:
    path = ensure_disposable_database()
    user_id = uuid.uuid4().hex
    raw_token = f"migration-roundtrip-{uuid.uuid4().hex}"
    first_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    second_hash = hashlib.sha256(first_hash.encode("utf-8")).hexdigest()
    expires_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    revoked_at = (
        datetime.now(UTC).replace(microsecond=0) - timedelta(hours=1)
    ).isoformat()

    run_alembic("downgrade", LEGACY_SESSION_REVISION)
    try:
        with connect(path) as connection:
            columns = table_columns(connection, "sessions")
            assert "token" in columns
            assert "token_hash" not in columns
            connection.execute(
                "INSERT INTO users (id, email, full_name, password_hash) "
                "VALUES (?, ?, ?, ?)",
                (
                    user_id,
                    f"migration-{user_id}@deltaforce.internal",
                    "Usuário de Migração",
                    "synthetic-password-hash",
                ),
            )
            connection.execute(
                "INSERT INTO sessions (token, user_id, expires_at, revoked_at) "
                "VALUES (?, ?, ?, ?)",
                (raw_token, user_id, expires_at, revoked_at),
            )
            connection.commit()

        run_alembic("upgrade", "head")
        with connect(path) as connection:
            columns = table_columns(connection, "sessions")
            assert "token_hash" in columns
            assert "token" not in columns
            row = connection.execute(
                "SELECT token_hash, user_id, expires_at, revoked_at "
                "FROM sessions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            assert row == (first_hash, user_id, expires_at, revoked_at)
            assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

        run_alembic("downgrade", LEGACY_SESSION_REVISION)
        with connect(path) as connection:
            row = connection.execute(
                "SELECT token, user_id, expires_at, revoked_at "
                "FROM sessions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            assert row == (first_hash, user_id, expires_at, revoked_at)

        run_alembic("upgrade", "head")
        with connect(path) as connection:
            row = connection.execute(
                "SELECT token_hash, user_id, expires_at, revoked_at "
                "FROM sessions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            assert row == (second_hash, user_id, expires_at, revoked_at)
    finally:
        run_alembic("upgrade", "head")
        with connect(path) as connection:
            connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
            connection.commit()


def test_audit_migration_round_trip_preserves_authentication_data() -> None:
    path = ensure_disposable_database()
    user_id = uuid.uuid4().hex
    token_hash = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    expires_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    try:
        with connect(path) as connection:
            assert "audit_events" in {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            connection.execute(
                "INSERT INTO users (id, email, full_name, password_hash) "
                "VALUES (?, ?, ?, ?)",
                (
                    user_id,
                    f"audit-migration-{user_id}@deltaforce.internal",
                    "Synthetic Migration User",
                    "synthetic-password-hash",
                ),
            )
            connection.execute(
                "INSERT INTO sessions (token_hash, user_id, expires_at) "
                "VALUES (?, ?, ?)",
                (token_hash, user_id, expires_at),
            )
            connection.commit()

        run_alembic("downgrade", PREVIOUS_AUDIT_REVISION)
        with connect(path) as connection:
            table_names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            assert "audit_events" not in table_names
            preserved_session = connection.execute(
                "SELECT user_id, expires_at FROM sessions WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
            assert preserved_session == (user_id, expires_at)

        run_alembic("upgrade", "head")
        with connect(path) as connection:
            table_names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            assert "audit_events" in table_names
            preserved_user = connection.execute(
                "SELECT id FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            assert preserved_user == (user_id,)
            index_names = {
                row[1] for row in connection.execute("PRAGMA index_list(audit_events)")
            }
            assert {
                "ix_audit_events_actor_user_id",
                "ix_audit_events_occurred_at_id",
            } <= index_names
            assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        run_alembic("upgrade", "head")
        with connect(path) as connection:
            connection.execute(
                "DELETE FROM sessions WHERE token_hash = ?", (token_hash,)
            )
            connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
            connection.commit()


def insert_audit_event(
    connection: sqlite3.Connection,
    *,
    actor_kind: str,
    actor_user_id: str | None,
    action: str = "auth.login",
    resource_type: str = "owner_account",
    result: str = "success",
) -> str:
    event_id = uuid.uuid4().hex
    connection.execute(
        """
        INSERT INTO audit_events (
            id, actor_kind, actor_user_id, action, resource_type,
            resource_id, result, context
        )
        VALUES (?, ?, ?, ?, ?, NULL, ?, ?)
        """,
        (event_id, actor_kind, actor_user_id, action, resource_type, result, "{}"),
    )
    connection.commit()
    return event_id


def test_audit_database_rejects_invalid_catalog_and_actor_identity() -> None:
    path = ensure_disposable_database()
    user_id = uuid.uuid4().hex
    event_id: str | None = None
    with connect(path) as connection:
        connection.execute(
            "INSERT INTO users (id, email, full_name, password_hash) "
            "VALUES (?, ?, ?, ?)",
            (
                user_id,
                f"audit-constraints-{user_id}@deltaforce.internal",
                "Synthetic Constraint User",
                "synthetic-password-hash",
            ),
        )
        connection.commit()

    rejected_cases: list[dict[str, object]] = [
        {"actor_kind": "anonymous", "actor_user_id": user_id},
        {"actor_kind": "authenticated", "actor_user_id": uuid.uuid4().hex},
        {"actor_kind": "anonymous", "actor_user_id": None, "result": "unknown"},
        {
            "actor_kind": "anonymous",
            "actor_user_id": None,
            "action": "person@example.com",
        },
        {
            "actor_kind": "anonymous",
            "actor_user_id": None,
            "resource_type": "raw-session-secret",
        },
    ]

    try:
        for values in rejected_cases:
            with connect(path) as connection:
                with pytest.raises(sqlite3.IntegrityError):
                    insert_audit_event(connection, **values)  # type: ignore[arg-type]

        with connect(path) as connection:
            event_id = insert_audit_event(
                connection,
                actor_kind="authenticated",
                actor_user_id=user_id,
            )

        with connect(path) as connection:
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
    finally:
        with connect(path) as connection:
            if event_id is not None:
                connection.execute("DELETE FROM audit_events WHERE id = ?", (event_id,))
            connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
            connection.commit()


def test_client_folder_migration_round_trip_restores_schema_and_audit_catalog() -> None:
    path = ensure_disposable_database()

    run_alembic("downgrade", PREVIOUS_CLIENT_FOLDER_REVISION)
    try:
        with connect(path) as connection:
            table_names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            assert "client_folders" not in table_names
            with pytest.raises(sqlite3.IntegrityError):
                insert_audit_event(
                    connection,
                    actor_kind="anonymous",
                    actor_user_id=None,
                    action="client_folder.created",
                    resource_type="client_folder",
                )

        run_alembic("upgrade", "head")
        with connect(path) as connection:
            table_names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            assert "client_folders" in table_names
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO client_folders (id, display_name, profile_data) "
                    "VALUES (?, ?, ?)",
                    (uuid.uuid4().hex, " ", "{}"),
                )
            event_id = insert_audit_event(
                connection,
                actor_kind="anonymous",
                actor_user_id=None,
                action="client_folder.created",
                resource_type="client_folder",
            )
            connection.execute("DELETE FROM audit_events WHERE id = ?", (event_id,))
            connection.commit()
    finally:
        run_alembic("upgrade", "head")


def test_client_folder_view_update_audit_migration_round_trip() -> None:
    path = ensure_disposable_database()

    run_alembic("downgrade", PREVIOUS_VIEW_UPDATE_REVISION)
    try:
        with connect(path) as connection:
            for action in ("client_folder.viewed", "client_folder.updated"):
                with pytest.raises(sqlite3.IntegrityError):
                    insert_audit_event(
                        connection,
                        actor_kind="anonymous",
                        actor_user_id=None,
                        action=action,
                        resource_type="client_folder",
                    )

        run_alembic("upgrade", "head")
        with connect(path) as connection:
            event_ids = [
                insert_audit_event(
                    connection,
                    actor_kind="anonymous",
                    actor_user_id=None,
                    action=action,
                    resource_type="client_folder",
                )
                for action in ("client_folder.viewed", "client_folder.updated")
            ]
            for event_id in event_ids:
                assert connection.execute(
                    "SELECT id FROM audit_events WHERE id = ?", (event_id,)
                ).fetchone() == (event_id,)

        with pytest.raises(subprocess.CalledProcessError):
            run_alembic("downgrade", PREVIOUS_VIEW_UPDATE_REVISION)

        with connect(path) as connection:
            for event_id in event_ids:
                assert connection.execute(
                    "SELECT id FROM audit_events WHERE id = ?", (event_id,)
                ).fetchone() == (event_id,)
                connection.execute("DELETE FROM audit_events WHERE id = ?", (event_id,))
            connection.commit()

        run_alembic("downgrade", PREVIOUS_VIEW_UPDATE_REVISION)
    finally:
        run_alembic("upgrade", "head")


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }


def _insert_document(
    connection: sqlite3.Connection, *, client_folder_id: str, storage_key: str
) -> str:
    document_id = uuid.uuid4().hex
    connection.execute(
        """
        INSERT INTO documents (
            id, client_folder_id, original_filename, storage_key,
            media_type, byte_size, checksum_sha256
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            client_folder_id,
            "contrato sintetico.pdf",
            storage_key,
            "application/pdf",
            1024,
            "c" * 64,
        ),
    )
    connection.commit()
    return document_id


def test_document_migration_round_trip_restores_schema_and_audit_catalog() -> None:
    path = ensure_disposable_database()
    folder_id = uuid.uuid4().hex

    run_alembic("downgrade", PREVIOUS_DOCUMENT_REVISION)
    try:
        with connect(path) as connection:
            assert "documents" not in _table_names(connection)
            with pytest.raises(sqlite3.IntegrityError):
                insert_audit_event(
                    connection,
                    actor_kind="anonymous",
                    actor_user_id=None,
                    action="document.stored",
                    resource_type="document",
                )

        run_alembic("upgrade", "head")
        with connect(path) as connection:
            assert "documents" in _table_names(connection)
            # Subconjunto: as anotações opcionais chegam na 0009.
            assert {
                "id",
                "client_folder_id",
                "original_filename",
                "storage_key",
                "media_type",
                "byte_size",
                "checksum_sha256",
                "stored_at",
            } <= table_columns(connection, "documents")
            connection.execute(
                "INSERT INTO client_folders (id, display_name, profile_data) "
                "VALUES (?, ?, ?)",
                (folder_id, "Cliente Sintético de Migration", "{}"),
            )
            connection.commit()

            # A FK só é efetiva com PRAGMA foreign_keys=ON em toda conexão.
            with pytest.raises(sqlite3.IntegrityError):
                _insert_document(
                    connection,
                    client_folder_id=uuid.uuid4().hex,
                    storage_key=f"aa/bb/{uuid.uuid4().hex}.pdf",
                )

            document_id = _insert_document(
                connection,
                client_folder_id=folder_id,
                storage_key=f"cc/dd/{uuid.uuid4().hex}.pdf",
            )
            # Uma pasta com documento não pode ser apagada por baixo dele.
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "DELETE FROM client_folders WHERE id = ?", (folder_id,)
                )

        # O rollback é recusado enquanto houver documento ou auditoria de documento.
        with pytest.raises(subprocess.CalledProcessError):
            run_alembic("downgrade", PREVIOUS_DOCUMENT_REVISION)

        with connect(path) as connection:
            connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            connection.commit()
            event_id = insert_audit_event(
                connection,
                actor_kind="anonymous",
                actor_user_id=None,
                action="document.stored",
                resource_type="document",
            )

        with pytest.raises(subprocess.CalledProcessError):
            run_alembic("downgrade", PREVIOUS_DOCUMENT_REVISION)

        with connect(path) as connection:
            connection.execute("DELETE FROM audit_events WHERE id = ?", (event_id,))
            connection.commit()

        run_alembic("downgrade", PREVIOUS_DOCUMENT_REVISION)
    finally:
        run_alembic("upgrade", "head")
        with connect(path) as connection:
            connection.execute("DELETE FROM client_folders WHERE id = ?", (folder_id,))
            connection.commit()


def test_document_annotation_migration_round_trip_keeps_columns_optional() -> None:
    path = ensure_disposable_database()
    folder_id = uuid.uuid4().hex

    run_alembic("downgrade", PREVIOUS_ANNOTATION_REVISION)
    try:
        with connect(path) as connection:
            columns = table_columns(connection, "documents")
            assert {"title", "category", "notes"}.isdisjoint(columns)
            for action in ("document.viewed", "document.exported"):
                with pytest.raises(sqlite3.IntegrityError):
                    insert_audit_event(
                        connection,
                        actor_kind="anonymous",
                        actor_user_id=None,
                        action=action,
                        resource_type="document",
                    )

        run_alembic("upgrade", "head")
        with connect(path) as connection:
            assert {"title", "category", "notes"} <= table_columns(
                connection, "documents"
            )
            connection.execute(
                "INSERT INTO client_folders (id, display_name, profile_data) "
                "VALUES (?, ?, ?)",
                (folder_id, "Cliente Sintético de Anotação", "{}"),
            )
            connection.commit()

            # Nenhuma anotação é obrigatória: o anexo entra sem título nem tipo.
            document_id = _insert_document(
                connection,
                client_folder_id=folder_id,
                storage_key=f"ef/01/{uuid.uuid4().hex}.pdf",
            )
            stored = connection.execute(
                "SELECT title, category, notes FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()
            assert stored == (None, None, None)

            event_id = insert_audit_event(
                connection,
                actor_kind="anonymous",
                actor_user_id=None,
                action="document.exported",
                resource_type="document",
            )

        # O rollback é recusado enquanto a auditoria de consulta/exportação existir.
        with pytest.raises(subprocess.CalledProcessError):
            run_alembic("downgrade", PREVIOUS_ANNOTATION_REVISION)

        with connect(path) as connection:
            connection.execute("DELETE FROM audit_events WHERE id = ?", (event_id,))
            connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            connection.commit()

        run_alembic("downgrade", PREVIOUS_ANNOTATION_REVISION)
    finally:
        run_alembic("upgrade", "head")
        with connect(path) as connection:
            connection.execute("DELETE FROM client_folders WHERE id = ?", (folder_id,))
            connection.commit()


def test_document_status_migration_backfills_and_protects_history() -> None:
    path = ensure_disposable_database()
    folder_id = uuid.uuid4().hex
    document_id: str | None = None

    run_alembic("downgrade", PREVIOUS_DOCUMENT_STATUS_REVISION)
    try:
        with connect(path) as connection:
            assert "status" not in table_columns(connection, "documents")
            with pytest.raises(sqlite3.IntegrityError):
                insert_audit_event(
                    connection,
                    actor_kind="anonymous",
                    actor_user_id=None,
                    action="document.status_updated",
                    resource_type="document",
                )
            connection.execute(
                "INSERT INTO client_folders (id, display_name, profile_data) "
                "VALUES (?, ?, ?)",
                (folder_id, "Cliente Sintético de Status", "{}"),
            )
            document_id = _insert_document(
                connection,
                client_folder_id=folder_id,
                storage_key=f"ab/23/{uuid.uuid4().hex}.pdf",
            )

        run_alembic("upgrade", "head")
        with connect(path) as connection:
            assert "status" in table_columns(connection, "documents")
            indexes = {
                row[1] for row in connection.execute("PRAGMA index_list(documents)")
            }
            assert "ix_documents_status" in indexes
            stored_status = connection.execute(
                "SELECT status FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
            assert stored_status == ("pending",)

            connection.execute(
                "UPDATE documents SET status = 'incorrect_incomplete' WHERE id = ?",
                (document_id,),
            )
            connection.commit()

        with pytest.raises(subprocess.CalledProcessError):
            run_alembic("downgrade", PREVIOUS_DOCUMENT_STATUS_REVISION)

        with connect(path) as connection:
            connection.execute(
                "UPDATE documents SET status = 'pending' WHERE id = ?", (document_id,)
            )
            event_id = insert_audit_event(
                connection,
                actor_kind="anonymous",
                actor_user_id=None,
                action="document.status_updated",
                resource_type="document",
            )

        with pytest.raises(subprocess.CalledProcessError):
            run_alembic("downgrade", PREVIOUS_DOCUMENT_STATUS_REVISION)

        with connect(path) as connection:
            connection.execute("DELETE FROM audit_events WHERE id = ?", (event_id,))
            connection.commit()

        run_alembic("downgrade", PREVIOUS_DOCUMENT_STATUS_REVISION)
        with connect(path) as connection:
            assert "status" not in table_columns(connection, "documents")
    finally:
        run_alembic("upgrade", "head")
        with connect(path) as connection:
            if document_id is not None:
                connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            connection.execute("DELETE FROM client_folders WHERE id = ?", (folder_id,))
            connection.commit()
