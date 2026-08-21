"""SQLite durability smoke test for the proposed production data path."""

from __future__ import annotations

import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from spike_runtime.security import RuntimeConfigurationError

DATABASE_FILENAME = "runtime-smoke.sqlite3"


@dataclass(frozen=True)
class SQLiteSmokeResult:
    journal_mode: str
    synchronous: int
    foreign_keys: bool
    persisted_after_reopen: bool
    rollback_clean: bool
    foreign_key_enforced: bool
    integrity_check: str

    @property
    def passed(self) -> bool:
        return (
            self.journal_mode == "wal"
            and self.synchronous == 2
            and self.foreign_keys
            and self.persisted_after_reopen
            and self.rollback_clean
            and self.foreign_key_enforced
            and self.integrity_check == "ok"
        )


def executable_root() -> Path:
    """Return the immutable binary/source tree used for separation checks."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def database_path_for(
    data_directory: Path,
    *,
    binary_root: Path | None = None,
) -> Path:
    """Create an external data directory and return its synthetic DB path."""

    resolved_data = data_directory.expanduser().resolve()
    resolved_binary = (binary_root or executable_root()).resolve()
    if resolved_data == resolved_binary or resolved_data.is_relative_to(
        resolved_binary
    ):
        raise RuntimeConfigurationError("data directory overlaps binary tree")

    resolved_data.mkdir(parents=True, exist_ok=True)
    return resolved_data / DATABASE_FILENAME


def _open_database(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, isolation_level=None, timeout=5.0)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS runtime_smoke_parent (
            id INTEGER PRIMARY KEY,
            marker TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS runtime_smoke_child (
            id INTEGER PRIMARY KEY,
            parent_id INTEGER NOT NULL
                REFERENCES runtime_smoke_parent(id),
            marker TEXT NOT NULL
        );
        """
    )


def _write_committed_synthetic_row(database_path: Path) -> None:
    with closing(_open_database(database_path)) as connection:
        _create_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute("DELETE FROM runtime_smoke_child")
            connection.execute("DELETE FROM runtime_smoke_parent")
            connection.execute(
                "INSERT INTO runtime_smoke_parent (id, marker) VALUES (1, ?)",
                ("synthetic-committed",),
            )
        except Exception:
            connection.execute("ROLLBACK")
            raise
        connection.execute("COMMIT")


def _exercise_uncommitted_rollback(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            "INSERT INTO runtime_smoke_parent (id, marker) VALUES (2, ?)",
            ("synthetic-uncommitted",),
        )
    finally:
        connection.execute("ROLLBACK")


def _foreign_key_is_enforced(connection: sqlite3.Connection) -> bool:
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            """
            INSERT INTO runtime_smoke_child (id, parent_id, marker)
            VALUES (1, 999, ?)
            """,
            ("synthetic-orphan",),
        )
    except sqlite3.IntegrityError:
        connection.execute("ROLLBACK")
        return True
    connection.execute("ROLLBACK")
    return False


def run_sqlite_smoke(database_path: Path) -> SQLiteSmokeResult:
    """Exercise settings, commit/reopen, rollback, FK, and integrity."""

    database_path = database_path.resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    _write_committed_synthetic_row(database_path)

    with closing(_open_database(database_path)) as connection:
        persisted = connection.execute(
            "SELECT marker FROM runtime_smoke_parent WHERE id = 1"
        ).fetchone() == ("synthetic-committed",)
        _exercise_uncommitted_rollback(connection)

    with closing(_open_database(database_path)) as connection:
        journal_mode = str(
            connection.execute("PRAGMA journal_mode").fetchone()[0]
        ).lower()
        synchronous = int(connection.execute("PRAGMA synchronous").fetchone()[0])
        foreign_keys = bool(connection.execute("PRAGMA foreign_keys").fetchone()[0])
        rollback_clean = (
            connection.execute(
                "SELECT COUNT(*) FROM runtime_smoke_parent WHERE id = 2"
            ).fetchone()[0]
            == 0
        )
        foreign_key_enforced = _foreign_key_is_enforced(connection)
        integrity = str(
            connection.execute("PRAGMA integrity_check").fetchone()[0]
        ).lower()

    result = SQLiteSmokeResult(
        journal_mode=journal_mode,
        synchronous=synchronous,
        foreign_keys=foreign_keys,
        persisted_after_reopen=persisted,
        rollback_clean=rollback_clean,
        foreign_key_enforced=foreign_key_enforced,
        integrity_check=integrity,
    )
    if not result.passed:
        raise RuntimeError("SQLite smoke test failed")
    return result
