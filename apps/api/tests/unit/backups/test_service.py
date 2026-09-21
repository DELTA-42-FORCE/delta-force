from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess

import pytest

from crm_api.infrastructure.backups.container import BackupPasswordOrIntegrityError
from crm_api.infrastructure.backups.media import BackupMediaPolicy
from crm_api.infrastructure.backups.service import (
    ACTIVE_DATABASE_NAME,
    ACTIVE_DOCUMENTS_NAME,
    BACKUP_EXTENSION,
    RESTORE_MARKER_NAME,
    BackupSourceIntegrityError,
    BackupServiceError,
    EncryptedBackupService,
    RestoreRequiresEmptyInstallationError,
    activate_pending_restore,
    is_empty_installation,
    _safe_remove_tree,
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
    return root, database, documents


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
    assert (target_root / RESTORE_MARKER_NAME).exists()

    assert activate_pending_restore(target_root) is True

    restored_document = documents.joinpath(*_STORAGE_KEY.split("/"))
    assert restored_document.read_bytes() == _DOCUMENT
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone() == (1,)
        assert connection.execute(
            "SELECT action FROM audit_events WHERE action = 'backup.restore_applied'"
        ).fetchone() == ("backup.restore_applied",)
    assert not (target_root / RESTORE_MARKER_NAME).exists()
    assert is_empty_installation(database, documents) is False


def test_wrong_password_cleans_plaintext_restore_staging(tmp_path: Path) -> None:
    backup = _create_backup(tmp_path)
    target_root, database, documents = _data_root(tmp_path / "target", populated=False)

    with pytest.raises(BackupPasswordOrIntegrityError):
        _service(target_root, database, documents).stage_restore(
            source_file=str(backup), passphrase="senha sintetica errada"
        )

    assert not (target_root / RESTORE_MARKER_NAME).exists()
    assert sorted(item.name for item in target_root.iterdir()) == [
        ACTIVE_DATABASE_NAME,
        ACTIVE_DOCUMENTS_NAME,
    ]


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


def test_corrupted_candidate_is_removed_without_touching_empty_installation(
    tmp_path: Path,
) -> None:
    backup = _create_backup(tmp_path)
    target_root, database, documents = _data_root(tmp_path / "target", populated=False)
    service = _service(target_root, database, documents)
    service.stage_restore(source_file=str(backup), passphrase="senha sintetica forte")
    candidate = next(target_root.glob("restore-candidate-*"))
    (candidate / ACTIVE_DATABASE_NAME).write_bytes(b"corrupted")

    with pytest.raises((BackupSourceIntegrityError, sqlite3.DatabaseError)):
        activate_pending_restore(target_root)

    assert is_empty_installation(database, documents) is True
    assert not (target_root / RESTORE_MARKER_NAME).exists()
    assert not candidate.exists()


def _create_windows_junction(link: Path, target: Path) -> None:
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.skipif(os.name != "nt", reason="junctions are Windows-specific")
def test_cleanup_rejects_candidate_junction_without_touching_target(
    tmp_path: Path,
) -> None:
    data_root, _, documents = _data_root(tmp_path / "target", populated=True)
    candidate = data_root / f"restore-candidate-{'0' * 32}"
    protected_document = documents.joinpath(*_STORAGE_KEY.split("/"))
    _create_windows_junction(candidate, documents)
    try:
        with pytest.raises(BackupServiceError, match="reparse point"):
            _safe_remove_tree(data_root, candidate)
        assert protected_document.read_bytes() == _DOCUMENT
    finally:
        if os.path.lexists(candidate):
            os.rmdir(candidate)


@pytest.mark.skipif(os.name != "nt", reason="junctions are Windows-specific")
def test_activation_rejects_candidate_junction_without_touching_documents(
    tmp_path: Path,
) -> None:
    data_root, _, documents = _data_root(tmp_path / "target", populated=True)
    candidate = data_root / f"restore-candidate-{'1' * 32}"
    marker = data_root / RESTORE_MARKER_NAME
    protected_document = documents.joinpath(*_STORAGE_KEY.split("/"))
    _create_windows_junction(candidate, documents)
    marker.write_text(
        json.dumps({"candidate": candidate.name, "version": 1}),
        encoding="ascii",
    )
    try:
        with pytest.raises(BackupServiceError):
            activate_pending_restore(data_root)
        assert protected_document.read_bytes() == _DOCUMENT
    finally:
        if os.path.lexists(candidate):
            os.rmdir(candidate)


@pytest.mark.skipif(os.name != "nt", reason="junctions are Windows-specific")
def test_rollback_rejects_junction_before_changing_active_data(
    tmp_path: Path,
) -> None:
    data_root, database, documents = _data_root(tmp_path / "target", populated=True)
    rollback = data_root / "restore-rollback"
    marker = data_root / RESTORE_MARKER_NAME
    protected_document = documents.joinpath(*_STORAGE_KEY.split("/"))
    _create_windows_junction(rollback, documents)
    marker.write_text("{}", encoding="ascii")
    try:
        with pytest.raises(BackupServiceError, match="rollback is invalid"):
            activate_pending_restore(data_root)
        assert database.is_file()
        assert protected_document.read_bytes() == _DOCUMENT
    finally:
        if os.path.lexists(rollback):
            os.rmdir(rollback)
