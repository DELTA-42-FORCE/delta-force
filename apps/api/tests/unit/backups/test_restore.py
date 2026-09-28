"""Testes sintéticos da validação/restauração isolada de backups."""

import errno
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tarfile

import pytest

from crm_api.infrastructure.backups.container import encrypt_payload
from crm_api.infrastructure.backups.restore import (
    InsufficientRestoreSpaceError,
    InvalidRestoreBackupError,
    _InvalidPayload,
    _validate_tar_size,
    stage_backup_restore,
)

_REVISION = "20260920_0016"
_KEY = "ab/cd/0123456789abcdef0123456789abcdef.pdf"
_DOCUMENT = b"%PDF-1.7\nconteudo sintetico\n%%EOF"
_PASSPHRASE = "senha sintetica forte"


@pytest.mark.parametrize(
    "manifest",
    [
        {"database": None, "documents": []},
        {"database": {}, "documents": None},
    ],
)
def test_tar_size_validation_rejects_unvalidated_manifest_types(
    tmp_path: Path, manifest: dict
) -> None:
    with pytest.raises(_InvalidPayload):
        _validate_tar_size(tmp_path / "payload.tar", manifest)


def _archive_member(name: str, size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.mode = 0o600
    return info


def _backup(
    tmp_path: Path,
    *,
    manifest_override: dict | None = None,
    tar_mutation: str | None = None,
) -> Path:
    database_path = tmp_path / "source.sqlite3"
    with sqlite3.connect(database_path) as database:
        database.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
        database.execute("INSERT INTO alembic_version VALUES (?)", (_REVISION,))
        database.execute(
            "CREATE TABLE documents (storage_key TEXT, byte_size INTEGER, "
            "checksum_sha256 TEXT)"
        )
        database.execute(
            "INSERT INTO documents VALUES (?, ?, ?)",
            (_KEY, len(_DOCUMENT), hashlib.sha256(_DOCUMENT).hexdigest()),
        )
    database_bytes = database_path.read_bytes()
    manifest = manifest_override or {
        "format_version": 1,
        "schema_revision": _REVISION,
        "database": {
            "path": "db.sqlite3",
            "size": len(database_bytes),
            "sha256": hashlib.sha256(database_bytes).hexdigest(),
        },
        "document_count": 1,
        "documents": [
            {
                "path": f"documents/{_KEY}",
                "storage_key": _KEY,
                "size": len(_DOCUMENT),
                "sha256": hashlib.sha256(_DOCUMENT).hexdigest(),
            }
        ],
    }
    manifest_bytes = json.dumps(
        manifest, sort_keys=True, separators=(",", ":")
    ).encode()
    payload = tmp_path / "payload.tar"
    import io

    with tarfile.open(payload, "w|", format=tarfile.USTAR_FORMAT) as archive:
        archive.addfile(
            _archive_member("manifest.json", len(manifest_bytes)),
            io.BytesIO(manifest_bytes),
        )
        archive.addfile(
            _archive_member("db.sqlite3", len(database_bytes)),
            io.BytesIO(database_bytes),
        )
        document_member = _archive_member(f"documents/{_KEY}", len(_DOCUMENT))
        if tar_mutation in {"symlink", "hardlink"}:
            document_member.type = (
                tarfile.SYMTYPE if tar_mutation == "symlink" else tarfile.LNKTYPE
            )
            document_member.linkname = "../../outside.pdf"
            document_member.size = 0
            archive.addfile(document_member)
        elif tar_mutation == "device":
            document_member.type = tarfile.CHRTYPE
            document_member.devmajor = 1
            document_member.devminor = 3
            document_member.size = 0
            archive.addfile(document_member)
        elif tar_mutation == "absolute-path":
            document_member.name = "/outside.pdf"
            archive.addfile(document_member, io.BytesIO(_DOCUMENT))
        else:
            archive.addfile(document_member, io.BytesIO(_DOCUMENT))
        if tar_mutation == "duplicate":
            archive.addfile(_archive_member("db.sqlite3", 0), io.BytesIO(b""))
    if tar_mutation == "truncate":
        payload.write_bytes(payload.read_bytes()[:-512])
    elif tar_mutation == "append":
        with payload.open("ab") as stream:
            stream.write(b"unexpected trailing bytes")
    elif tar_mutation == "member-padding":
        with tarfile.open(payload, "r:") as archive:
            manifest_member = archive.next()
            assert manifest_member is not None
            padding_offset = manifest_member.offset_data + manifest_member.size
            assert manifest_member.size % 512 != 0
        with payload.open("r+b") as stream:
            stream.seek(padding_offset)
            stream.write(b"X")
    elif tar_mutation == "end-padding":
        with payload.open("r+b") as stream:
            stream.seek(-1, os.SEEK_END)
            stream.write(b"X")
    source = tmp_path / "synthetic.dfcrmbak"
    encrypt_payload(
        payload_path=payload,
        destination_path=source,
        passphrase=_PASSPHRASE,
        app_version="0.1.0",
        created_at="2026-09-25T00:00:00Z",
        schema_revision=_REVISION,
    )
    return source


def test_restore_stages_verified_candidate_without_touching_active_files(
    tmp_path: Path,
) -> None:
    source = _backup(tmp_path)
    active = tmp_path / "active.sqlite3"
    active.write_bytes(b"active synthetic database")
    staging = tmp_path / "private-staging"

    with stage_backup_restore(
        source_path=source,
        passphrase=_PASSPHRASE,
        temporary_root=staging,
    ) as candidate:
        assert candidate.schema_revision == _REVISION
        assert candidate.database_path.read_bytes() != active.read_bytes()
        restored_document = candidate.documents_root.joinpath(*_KEY.split("/"))
        assert restored_document.read_bytes() == _DOCUMENT
        assert active.read_bytes() == b"active synthetic database"

    assert active.read_bytes() == b"active synthetic database"
    assert list(staging.iterdir()) == []


@pytest.mark.parametrize(
    "mutation",
    [
        "truncate",
        "append",
        "member-padding",
        "end-padding",
        "symlink",
        "hardlink",
        "device",
        "absolute-path",
        "duplicate",
    ],
)
def test_restore_rejects_truncated_extra_or_noncanonical_tar_bytes(
    tmp_path: Path, mutation: str
) -> None:
    source = _backup(tmp_path, tar_mutation=mutation)
    staging = tmp_path / "private-staging"

    with pytest.raises(InvalidRestoreBackupError):
        with stage_backup_restore(
            source_path=source,
            passphrase=_PASSPHRASE,
            temporary_root=staging,
        ):
            pytest.fail("non-canonical tar size must not yield a candidate")

    assert list(staging.iterdir()) == []


def test_restore_wrong_password_has_generic_error_and_cleans_staging(
    tmp_path: Path,
) -> None:
    source = _backup(tmp_path)
    staging = tmp_path / "private-staging"

    with pytest.raises(InvalidRestoreBackupError) as error:
        with stage_backup_restore(
            source_path=source,
            passphrase="senha errada sintetica",
            temporary_root=staging,
        ):
            pytest.fail("wrong password must not yield a candidate")

    assert "senha" not in str(error.value).lower()
    assert list(staging.iterdir()) == []


def test_restore_rejects_traversal_before_materializing_files(tmp_path: Path) -> None:
    source = _backup(
        tmp_path,
        manifest_override={
            "format_version": 1,
            "schema_revision": _REVISION,
            "database": {"path": "../outside.sqlite3", "size": 1, "sha256": "0" * 64},
            "document_count": 0,
            "documents": [],
        },
    )
    staging = tmp_path / "private-staging"

    with pytest.raises(InvalidRestoreBackupError):
        with stage_backup_restore(
            source_path=source,
            passphrase=_PASSPHRASE,
            temporary_root=staging,
        ):
            pytest.fail("path traversal must not yield a candidate")

    assert not (tmp_path / "outside.sqlite3").exists()
    assert list(staging.iterdir()) == []


def test_restore_checks_space_before_running_scrypt(
    tmp_path: Path, monkeypatch
) -> None:
    source = _backup(tmp_path)
    staging = tmp_path / "private-staging"
    monkeypatch.setattr(
        "crm_api.infrastructure.backups.restore.shutil.disk_usage",
        lambda _path: type("Usage", (), {"free": 0})(),
    )
    monkeypatch.setattr(
        "crm_api.infrastructure.backups.container.hashlib.scrypt",
        lambda *_args, **_kwargs: pytest.fail("KDF must not run without space"),
    )

    with pytest.raises(InsufficientRestoreSpaceError):
        with stage_backup_restore(
            source_path=source,
            passphrase=_PASSPHRASE,
            temporary_root=staging,
        ):
            pytest.fail("insufficient space must stop restore")

    assert list(staging.iterdir()) == []


def test_restore_reports_space_lost_during_decryption_and_cleans_staging(
    tmp_path: Path, monkeypatch
) -> None:
    source = _backup(tmp_path)
    staging = tmp_path / "private-staging"

    def fail_decryption(**_kwargs) -> None:
        raise OSError(errno.ENOSPC, "synthetic disk full")

    monkeypatch.setattr(
        "crm_api.infrastructure.backups.restore.decrypt_payload", fail_decryption
    )

    with pytest.raises(InsufficientRestoreSpaceError):
        with stage_backup_restore(
            source_path=source,
            passphrase=_PASSPHRASE,
            temporary_root=staging,
        ):
            pytest.fail("disk full during decryption must not yield a candidate")

    assert list(staging.iterdir()) == []
