from pathlib import Path

import pytest

from crm_api.core.config import DOCUMENTS_DIRECTORY_NAME, get_settings
from crm_api.desktop_server import (
    _database_url,
    _read_bootstrap_secret,
    provision_desktop_database,
)
from crm_api.infrastructure.documents.storage import (
    INCOMING_DIRECTORY_NAME,
    provision_document_storage,
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


def test_desktop_data_directory_keeps_database_and_documents_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O backup da #44 depende de banco e documentos na mesma árvore de dados."""
    database_path = provision_desktop_database(tmp_path)
    documents_root = provision_document_storage(tmp_path / DOCUMENTS_DIRECTORY_NAME)

    assert documents_root.parent == database_path.parent
    assert (documents_root / INCOMING_DIRECTORY_NAME).is_dir()

    monkeypatch.delenv("DOCUMENTS_ROOT", raising=False)
    monkeypatch.setenv("DATABASE_URL", _database_url(database_path))
    get_settings.cache_clear()
    try:
        assert get_settings().documents_root_path == documents_root.resolve()
    finally:
        get_settings.cache_clear()
