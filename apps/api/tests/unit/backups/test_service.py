from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess

import pytest

from crm_api.infrastructure.backups.container import BackupPasswordOrIntegrityError
from crm_api.infrastructure.backups import generations
from crm_api.infrastructure.backups.media import BackupMediaPolicy
from crm_api.infrastructure.backups.generations import (
    ACTIVATION_JOURNAL_NAME,
    GENERATIONS_DIRECTORY_NAME,
    ActiveGeneration,
    GenerationLayoutError,
    discard_generation,
    provision_generation_layout,
    read_active_generation,
)
from crm_api.infrastructure.backups.service import (
    ACTIVE_DATABASE_NAME,
    ACTIVE_DOCUMENTS_NAME,
    BACKUP_EXTENSION,
    BackupSourceIntegrityError,
    BackupServiceError,
    EncryptedBackupService,
    RestoreRequiresEmptyInstallationError,
    activate_pending_restore,
    is_empty_installation,
)

_REVISION = "synthetic_revision"
_STORAGE_KEY = "00/00/00000000000000000000000000000001.pdf"
_DOCUMENT = b"%PDF-1.7\nsynthetic backup document\n%%EOF"


def _database(path: Path, *, populated: bool) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript("""
            CREATE TABLE alembic_version (version_num TEXT NOT NULL);
            CREATE TABLE users (id TEXT PRIMARY KEY);
            CREATE TABLE client_folders (id TEXT PRIMARY KEY);
            CREATE TABLE documents (
                storage_key TEXT NOT NULL UNIQUE,
                byte_size INTEGER NOT NULL,
                checksum_sha256 TEXT NOT NULL
            );
            CREATE TABLE message_templates (id TEXT PRIMARY KEY);
            CREATE TABLE audit_events (
                id TEXT PRIMARY KEY,
                occurred_at TEXT NOT NULL,
                actor_kind TEXT NOT NULL,
                actor_user_id TEXT,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT,
                result TEXT NOT NULL,
                context TEXT NOT NULL
            );
            """)
        connection.execute("INSERT INTO alembic_version VALUES (?)", (_REVISION,))
        if populated:
            import hashlib

            connection.execute("INSERT INTO users VALUES ('synthetic-owner')")
            connection.execute("INSERT INTO client_folders VALUES ('synthetic-client')")
            connection.execute(
                "INSERT INTO documents VALUES (?, ?, ?)",
                (_STORAGE_KEY, len(_DOCUMENT), hashlib.sha256(_DOCUMENT).hexdigest()),
            )
        connection.commit()


def _data_root(root: Path, *, populated: bool) -> tuple[Path, Path, Path]:
    root.mkdir()
    database = root / ACTIVE_DATABASE_NAME
    documents = root / ACTIVE_DOCUMENTS_NAME
    (documents / "_incoming").mkdir(parents=True)
    _database(database, populated=populated)
    if populated:
        document = documents.joinpath(*_STORAGE_KEY.split("/"))
        document.parent.mkdir(parents=True)
        document.write_bytes(_DOCUMENT)
    active = provision_generation_layout(root)
    return root, active.database_path, active.documents_root


def _service(
    data_root: Path, database: Path, documents: Path
) -> EncryptedBackupService:
    return EncryptedBackupService(
        data_root=data_root,
        database_path=database,
        documents_root=documents,
        media_policy=BackupMediaPolicy(
            data_root=data_root, allow_local_destination=True
        ),
    )


def _create_backup(tmp_path: Path) -> Path:
    source_root, database, documents = _data_root(tmp_path / "source", populated=True)
    destination = tmp_path / "external"
    destination.mkdir()
    result = _service(source_root, database, documents).create_backup(
        destination_directory=str(destination),
        passphrase="senha sintetica forte",
    )
    assert result.document_count == 1
    assert result.filename.endswith(BACKUP_EXTENSION)
    return destination / result.filename


def test_backup_restores_an_empty_installation_after_restart(tmp_path: Path) -> None:
    backup = _create_backup(tmp_path)
    target_root, database, documents = _data_root(tmp_path / "target", populated=False)
    service = _service(target_root, database, documents)

    staged = service.stage_restore(
        source_file=str(backup), passphrase="senha sintetica forte"
    )

    assert staged.requires_restart is True
    assert staged.document_count == 1
    assert is_empty_installation(database, documents) is True
    assert (target_root / ACTIVATION_JOURNAL_NAME).exists()

    assert activate_pending_restore(target_root) is True

    active = read_active_generation(target_root)
    assert active is not None
    restored_document = active.documents_root.joinpath(*_STORAGE_KEY.split("/"))
    assert restored_document.read_bytes() == _DOCUMENT
    with closing(sqlite3.connect(active.database_path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone() == (1,)
        assert connection.execute(
            "SELECT action FROM audit_events WHERE action = 'backup.restore_applied'"
        ).fetchone() == ("backup.restore_applied",)
    assert not (target_root / ACTIVATION_JOURNAL_NAME).exists()
    assert is_empty_installation(active.database_path, active.documents_root) is False


def test_wrong_password_cleans_plaintext_restore_staging(tmp_path: Path) -> None:
    backup = _create_backup(tmp_path)
    target_root, database, documents = _data_root(tmp_path / "target", populated=False)

    with pytest.raises(BackupPasswordOrIntegrityError):
        _service(target_root, database, documents).stage_restore(
            source_file=str(backup), passphrase="senha sintetica errada"
        )

    assert not (target_root / ACTIVATION_JOURNAL_NAME).exists()
    generations = target_root / GENERATIONS_DIRECTORY_NAME
    assert len(list(generations.iterdir())) == 1


def test_backup_refuses_document_that_disagrees_with_database(tmp_path: Path) -> None:
    source_root, database, documents = _data_root(tmp_path / "source", populated=True)
    documents.joinpath(*_STORAGE_KEY.split("/")).write_bytes(b"changed")
    destination = tmp_path / "external"
    destination.mkdir()

    with pytest.raises(BackupSourceIntegrityError):
        _service(source_root, database, documents).create_backup(
            destination_directory=str(destination),
            passphrase="senha sintetica forte",
        )

    assert list(destination.iterdir()) == []


def test_restore_never_replaces_a_nonempty_installation(tmp_path: Path) -> None:
    backup = _create_backup(tmp_path)
    target_root, database, documents = _data_root(tmp_path / "target", populated=True)

    with pytest.raises(RestoreRequiresEmptyInstallationError):
        _service(target_root, database, documents).stage_restore(
            source_file=str(backup), passphrase="senha sintetica forte"
        )

    assert documents.joinpath(*_STORAGE_KEY.split("/")).read_bytes() == _DOCUMENT


def test_documents_without_database_are_not_treated_as_empty(tmp_path: Path) -> None:
    documents = tmp_path / ACTIVE_DOCUMENTS_NAME
    documents.mkdir()
    (documents / "orphan.pdf").write_bytes(_DOCUMENT)

    assert is_empty_installation(tmp_path / ACTIVE_DATABASE_NAME, documents) is False


def test_explicit_replacement_switches_one_generation_after_validation(
    tmp_path: Path,
) -> None:
    backup = _create_backup(tmp_path)
    target_root, database, documents = _data_root(tmp_path / "target", populated=True)
    previous = read_active_generation(target_root)
    assert previous is not None

    _service(target_root, database, documents).stage_restore(
        source_file=str(backup),
        passphrase="senha sintetica forte",
        replace_existing=True,
    )

    assert read_active_generation(target_root) == previous
    assert activate_pending_restore(target_root) is True
    active = read_active_generation(target_root)
    assert active is not None and active.name != previous.name
    assert not previous.root.exists()
    assert (
        active.documents_root.joinpath(*_STORAGE_KEY.split("/")).read_bytes()
        == _DOCUMENT
    )


def test_corrupted_candidate_is_removed_without_touching_empty_installation(
    tmp_path: Path,
) -> None:
    backup = _create_backup(tmp_path)
    target_root, database, documents = _data_root(tmp_path / "target", populated=False)
    service = _service(target_root, database, documents)
    service.stage_restore(source_file=str(backup), passphrase="senha sintetica forte")
    journal = json.loads(
        (target_root / ACTIVATION_JOURNAL_NAME).read_text(encoding="ascii")
    )
    candidate = target_root / GENERATIONS_DIRECTORY_NAME / journal["candidate"]
    (candidate / ACTIVE_DATABASE_NAME).write_bytes(b"corrupted")
    previous = read_active_generation(target_root)

    with pytest.raises((BackupServiceError, sqlite3.DatabaseError)):
        activate_pending_restore(target_root)

    assert is_empty_installation(database, documents) is True
    assert read_active_generation(target_root) == previous
    assert not (target_root / ACTIVATION_JOURNAL_NAME).exists()
    assert not candidate.exists()


def test_activation_recovers_if_pointer_switched_before_journal_phase(
    tmp_path: Path,
) -> None:
    backup = _create_backup(tmp_path)
    target_root, database, documents = _data_root(tmp_path / "target", populated=False)
    _service(target_root, database, documents).stage_restore(
        source_file=str(backup), passphrase="senha sintetica forte"
    )
    journal = json.loads(
        (target_root / ACTIVATION_JOURNAL_NAME).read_text(encoding="ascii")
    )
    generations._write_pointer(target_root, journal["candidate"])

    assert activate_pending_restore(target_root) is True
    active = read_active_generation(target_root)
    assert active is not None and active.name == journal["candidate"]
    assert not (target_root / ACTIVATION_JOURNAL_NAME).exists()


def test_activation_rolls_pointer_back_when_final_confirmation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup = _create_backup(tmp_path)
    target_root, database, documents = _data_root(tmp_path / "target", populated=True)
    previous = read_active_generation(target_root)
    assert previous is not None
    _service(target_root, database, documents).stage_restore(
        source_file=str(backup),
        passphrase="senha sintetica forte",
        replace_existing=True,
    )
    monkeypatch.setattr(
        generations,
        "_record_restore_audit",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("synthetic final confirmation failure")
        ),
    )

    with pytest.raises(RuntimeError, match="synthetic final confirmation failure"):
        activate_pending_restore(target_root)

    assert read_active_generation(target_root) == previous
    assert (
        previous.documents_root.joinpath(*_STORAGE_KEY.split("/")).read_bytes()
        == _DOCUMENT
    )
    assert not (target_root / ACTIVATION_JOURNAL_NAME).exists()


def _create_windows_junction(link: Path, target: Path) -> None:
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.skipif(os.name != "nt", reason="junctions are Windows-specific")
def test_generation_cleanup_rejects_junction_without_touching_target(
    tmp_path: Path,
) -> None:
    data_root, _, documents = _data_root(tmp_path / "target", populated=True)
    candidate = data_root / GENERATIONS_DIRECTORY_NAME / f"generation-{'0' * 32}"
    protected_document = documents.joinpath(*_STORAGE_KEY.split("/"))
    _create_windows_junction(candidate, documents)
    try:
        with pytest.raises(GenerationLayoutError, match="link"):
            discard_generation(
                data_root,
                ActiveGeneration(name=candidate.name, root=candidate),
            )
        assert protected_document.read_bytes() == _DOCUMENT
    finally:
        if os.path.lexists(candidate):
            os.rmdir(candidate)
