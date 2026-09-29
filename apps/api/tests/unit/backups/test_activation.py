"""Testes de ativação atômica e recuperação após interrupção."""

import hashlib
import json
from pathlib import Path
import sqlite3

import pytest
from alembic.script import ScriptDirectory

from crm_api.desktop_server import _alembic_config, provision_desktop_database
from crm_api.infrastructure.backups.activation import (
    RestoreActivationError,
    RestoreConfirmationRequired,
    activate_restore_candidate,
    generation_paths,
    load_active_generation,
)
from crm_api.infrastructure.documents.storage import provision_document_storage

_DOCUMENT_KEY = "ab/cd/0123456789abcdef0123456789abcdef.pdf"
_DOCUMENT_BYTES = b"conteudo sintetico do PDF"


def _initialize_legacy(paths) -> None:
    provision_desktop_database(paths.root)
    provision_document_storage(paths.documents_root)


def _new_candidate(root: Path, *, clients: int = 0) -> Path:
    documents_root = root / "documents"
    documents_root.mkdir(parents=True)
    document_path = documents_root / _DOCUMENT_KEY
    document_path.parent.mkdir(parents=True)
    document_path.write_bytes(_DOCUMENT_BYTES)
    revision = ScriptDirectory.from_config(
        _alembic_config(root / "crm.sqlite3")
    ).get_current_head()
    database_path = root / "db.sqlite3"
    with sqlite3.connect(database_path) as database:
        database.executescript(
            "CREATE TABLE alembic_version (version_num TEXT NOT NULL);"
            "CREATE TABLE documents (storage_key TEXT, byte_size INTEGER, "
            "checksum_sha256 TEXT);"
            "CREATE TABLE client_folders (id TEXT PRIMARY KEY, "
            "display_name TEXT NOT NULL, profile_data TEXT NOT NULL, "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL);"
        )
        database.execute("INSERT INTO alembic_version VALUES (?)", (revision,))
        database.execute(
            "INSERT INTO documents VALUES (?, ?, ?)",
            (
                _DOCUMENT_KEY,
                len(_DOCUMENT_BYTES),
                hashlib.sha256(_DOCUMENT_BYTES).hexdigest(),
            ),
        )
        database.executemany(
            "INSERT INTO client_folders VALUES (?, ?, ?, ?, ?)",
            [
                (f"candidate-{index}", "Sintético", "{}", "2026-01-01", "2026-01-01")
                for index in range(clients)
            ],
        )
    return root


def _staged_candidate(tmp_path: Path, *, clients: int = 0) -> Path:
    return _new_candidate(
        tmp_path / "restore-staging" / "backup-restore-test" / "candidate",
        clients=clients,
    )


def _active_generation(data_directory: Path) -> str:
    pointer = json.loads(
        (data_directory / "active-generation.json").read_text(encoding="utf-8")
    )
    return pointer["generation"]


def test_first_boot_selects_legacy_database_and_documents_as_one_generation(
    tmp_path: Path,
) -> None:
    paths = load_active_generation(tmp_path, initialize_legacy=_initialize_legacy)

    assert paths.generation_id == "legacy"
    assert paths.database_path == tmp_path / "crm.sqlite3"
    assert paths.documents_root == tmp_path / "documents"
    assert _active_generation(tmp_path) == "legacy"


def test_bootstrap_removes_only_known_stale_restore_workspaces(tmp_path: Path) -> None:
    staging_root = tmp_path / "restore-staging"
    stale_workspace = staging_root / "backup-restore-interrupted"
    unrelated_workspace = staging_root / "keep-this-directory"
    (stale_workspace / "candidate").mkdir(parents=True)
    unrelated_workspace.mkdir()

    load_active_generation(tmp_path, initialize_legacy=_initialize_legacy)

    assert not stale_workspace.exists()
    assert unrelated_workspace.is_dir()


def test_empty_install_can_activate_candidate_without_replacement_confirmation(
    tmp_path: Path,
) -> None:
    load_active_generation(tmp_path, initialize_legacy=_initialize_legacy)
    candidate = _staged_candidate(tmp_path)

    result = activate_restore_candidate(
        data_directory=tmp_path,
        candidate_root=candidate,
        confirm_replacement=False,
        close_active_connections=lambda: None,
    )

    assert _active_generation(tmp_path) == result.generation_id
    active = generation_paths(tmp_path, result.generation_id)
    assert active.database_path.is_file()
    assert (active.documents_root / _DOCUMENT_KEY).read_bytes() == _DOCUMENT_BYTES
    assert result.previous_generation_id == "legacy"
    assert not (tmp_path / "crm.sqlite3").exists()
    booted = load_active_generation(tmp_path, initialize_legacy=_initialize_legacy)
    assert booted.generation_id == result.generation_id
    assert booted.database_path == active.database_path
    assert booted.documents_root == active.documents_root


def test_existing_data_requires_confirmation_and_returns_synthetic_summary(
    tmp_path: Path,
) -> None:
    legacy = load_active_generation(tmp_path, initialize_legacy=_initialize_legacy)
    with sqlite3.connect(legacy.database_path) as database:
        database.execute(
            "INSERT INTO client_folders "
            "(id, display_name, profile_data, created_at, updated_at) "
            "VALUES ('legacy-1', 'Sintético', '{}', '2026-01-01', '2026-01-01')"
        )
    candidate = _staged_candidate(tmp_path, clients=2)

    with pytest.raises(RestoreConfirmationRequired) as error:
        activate_restore_candidate(
            data_directory=tmp_path,
            candidate_root=candidate,
            confirm_replacement=False,
            close_active_connections=lambda: None,
        )

    assert error.value.summary.current_records["clients"] == 1
    assert error.value.summary.candidate_records["clients"] == 2
    assert _active_generation(tmp_path) == "legacy"


def test_unknown_nonempty_table_conservatively_requires_confirmation(
    tmp_path: Path,
) -> None:
    legacy = load_active_generation(tmp_path, initialize_legacy=_initialize_legacy)
    with sqlite3.connect(legacy.database_path) as database:
        database.execute("CREATE TABLE future_sensitive_records (value TEXT)")
        database.execute("INSERT INTO future_sensitive_records VALUES ('synthetic')")
    candidate = _staged_candidate(tmp_path)

    with pytest.raises(RestoreConfirmationRequired) as error:
        activate_restore_candidate(
            data_directory=tmp_path,
            candidate_root=candidate,
            confirm_replacement=False,
            close_active_connections=lambda: None,
        )

    assert error.value.summary.current_records["other_tables"] == 1
    assert _active_generation(tmp_path) == "legacy"


@pytest.mark.parametrize(
    "interrupt_phase",
    ["prepared", "candidate_ready", "pointer", "switched", "validated"],
)
def test_startup_completes_activation_interrupted_at_each_durable_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interrupt_phase: str,
) -> None:
    load_active_generation(tmp_path, initialize_legacy=_initialize_legacy)
    candidate = _staged_candidate(tmp_path)
    from crm_api.infrastructure.backups import activation

    write_pointer = activation._write_pointer
    write_journal = activation._write_journal

    def switch_then_interrupt(data_directory: Path, generation_id: str) -> None:
        write_pointer(data_directory, generation_id)
        if interrupt_phase == "pointer" and generation_id != "legacy":
            raise OSError("synthetic interruption after durable pointer switch")

    def journal_then_interrupt(
        data_directory: Path, journal: dict[str, str | int]
    ) -> None:
        write_journal(data_directory, journal)
        if journal["phase"] == interrupt_phase:
            raise OSError("synthetic interruption after durable journal phase")

    monkeypatch.setattr(activation, "_write_pointer", switch_then_interrupt)
    monkeypatch.setattr(activation, "_write_journal", journal_then_interrupt)
    with pytest.raises(RestoreActivationError):
        activate_restore_candidate(
            data_directory=tmp_path,
            candidate_root=candidate,
            confirm_replacement=False,
            close_active_connections=lambda: None,
        )
    journal = json.loads(
        (tmp_path / "restore-activation.json").read_text(encoding="utf-8")
    )
    candidate_generation = journal["candidate"]
    assert (tmp_path / "restore-activation.json").is_file()

    monkeypatch.setattr(activation, "_write_pointer", write_pointer)
    monkeypatch.setattr(activation, "_write_journal", write_journal)
    booted = load_active_generation(tmp_path, initialize_legacy=_initialize_legacy)

    expected_generation = (
        "legacy" if interrupt_phase == "prepared" else candidate_generation
    )
    assert _active_generation(tmp_path) == expected_generation
    assert booted.generation_id == expected_generation
    assert not (tmp_path / "restore-activation.json").exists()
    if expected_generation == "legacy":
        assert (tmp_path / "crm.sqlite3").is_file()
    else:
        assert not (tmp_path / "crm.sqlite3").exists()


def test_startup_rolls_back_when_candidate_is_damaged_after_interruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    load_active_generation(tmp_path, initialize_legacy=_initialize_legacy)
    candidate = _staged_candidate(tmp_path)
    from crm_api.infrastructure.backups import activation

    write_pointer = activation._write_pointer

    def switch_then_interrupt(data_directory: Path, generation_id: str) -> None:
        write_pointer(data_directory, generation_id)
        if generation_id != "legacy":
            raise OSError("synthetic interruption after durable pointer switch")

    monkeypatch.setattr(activation, "_write_pointer", switch_then_interrupt)
    with pytest.raises(RestoreActivationError):
        activate_restore_candidate(
            data_directory=tmp_path,
            candidate_root=candidate,
            confirm_replacement=False,
            close_active_connections=lambda: None,
        )
    candidate_generation = _active_generation(tmp_path)
    active = generation_paths(tmp_path, candidate_generation)
    (active.documents_root / _DOCUMENT_KEY).write_bytes(b"damaged synthetic content")

    monkeypatch.setattr(activation, "_write_pointer", write_pointer)
    write_journal = activation._write_journal

    def fail_after_rollback_phase(
        data_directory: Path, journal: dict[str, str | int]
    ) -> None:
        write_journal(data_directory, journal)
        if journal["phase"] == "rolling_back":
            raise OSError("synthetic interruption during rollback")

    monkeypatch.setattr(activation, "_write_journal", fail_after_rollback_phase)
    with pytest.raises(OSError, match="during rollback"):
        load_active_generation(tmp_path, initialize_legacy=_initialize_legacy)
    assert _active_generation(tmp_path) == candidate_generation

    monkeypatch.setattr(activation, "_write_journal", write_journal)
    booted = load_active_generation(tmp_path, initialize_legacy=_initialize_legacy)

    assert _active_generation(tmp_path) == "legacy"
    assert booted.generation_id == "legacy"
    assert not active.root.exists()
    assert (tmp_path / "crm.sqlite3").is_file()


def test_rejects_pointer_path_traversal(tmp_path: Path) -> None:
    (tmp_path / "active-generation.json").write_text(
        '{"format_version":1,"generation":"../outside"}', encoding="utf-8"
    )

    with pytest.raises(RestoreActivationError):
        load_active_generation(tmp_path, initialize_legacy=_initialize_legacy)
