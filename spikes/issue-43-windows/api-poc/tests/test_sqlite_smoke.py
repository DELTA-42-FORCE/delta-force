import sqlite3
from pathlib import Path

import pytest

from spike_runtime.security import RuntimeConfigurationError
from spike_runtime.sqlite_smoke import database_path_for, run_sqlite_smoke


def test_database_path_must_be_outside_the_binary_tree(tmp_path: Path) -> None:
    binary_root = tmp_path / "release"
    binary_root.mkdir()

    with pytest.raises(RuntimeConfigurationError):
        database_path_for(binary_root / "data", binary_root=binary_root)

    external_path = database_path_for(tmp_path / "state", binary_root=binary_root)
    assert external_path.parent == (tmp_path / "state").resolve()


def test_sqlite_smoke_proves_required_durability_invariants(tmp_path: Path) -> None:
    database_path = tmp_path / "external-data" / "runtime-smoke.sqlite3"
    result = run_sqlite_smoke(database_path)

    assert result.passed
    assert result.journal_mode == "wal"
    assert result.synchronous == 2
    assert result.foreign_keys is True
    assert result.persisted_after_reopen is True
    assert result.rollback_clean is True
    assert result.foreign_key_enforced is True
    assert result.integrity_check == "ok"

    with sqlite3.connect(database_path) as reopened:
        assert reopened.execute(
            "SELECT marker FROM runtime_smoke_parent WHERE id = 1"
        ).fetchone() == ("synthetic-committed",)
        assert reopened.execute(
            "SELECT COUNT(*) FROM runtime_smoke_parent WHERE id = 2"
        ).fetchone() == (0,)
