from pathlib import Path

import pytest

from crm_api.desktop_server import (
    _database_url,
    _read_bootstrap_secret,
    provision_desktop_database,
)


def test_desktop_database_url_uses_an_absolute_file_path(tmp_path: Path) -> None:
    url = _database_url(tmp_path / "crm.sqlite3")

    assert url.startswith("sqlite+aiosqlite:///")
    assert url.endswith("/crm.sqlite3")


def test_desktop_bootstrap_secret_reader_rejects_empty_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class EmptyInput:
        def readline(self, size: int) -> bytes:
            assert size > 0
            return b""

    class Stdin:
        buffer = EmptyInput()

    monkeypatch.setattr("sys.stdin", Stdin())

    with pytest.raises(RuntimeError, match="bootstrap"):
        _read_bootstrap_secret()


def test_first_desktop_execution_publishes_only_a_migrated_sqlite_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    active_path = provision_desktop_database(tmp_path)

    assert active_path.name == "crm.sqlite3"
    assert active_path.exists()
    assert not (tmp_path / "crm.sqlite3.candidate").exists()
    assert provision_desktop_database(tmp_path) == active_path
    assert capsys.readouterr().out == ""
