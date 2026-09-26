"""Testes sintéticos do snapshot SQLite e do TAR determinístico."""

import hashlib
import json
from pathlib import Path
import sqlite3
import tarfile

import pytest

from crm_api.infrastructure.backups.snapshot import (
    BackupSnapshotError,
    build_backup_payload,
)

_KEY = "ab/cd/0123456789abcdef0123456789abcdef.pdf"
_CONTENT = b"%PDF-1.7\nconteudo sintetico\n%%EOF"


def _database(path: Path, *, content: bytes = _CONTENT) -> Path:
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO alembic_version(version_num) VALUES (?)",
            ("20260920_0016",),
        )
        connection.execute(
            "CREATE TABLE documents (storage_key TEXT, byte_size INTEGER, "
            "checksum_sha256 TEXT)"
        )
        connection.execute(
            "INSERT INTO documents VALUES (?, ?, ?)",
            (_KEY, len(content), hashlib.sha256(content).hexdigest()),
        )
    return path


def _document_root(path: Path, *, content: bytes = _CONTENT) -> Path:
    root = path / "documents"
    document = root.joinpath(*_KEY.split("/"))
    document.parent.mkdir(parents=True)
    document.write_bytes(content)
    return root


def test_snapshot_contains_only_snapshot_references_and_canonical_manifest(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path / "crm.sqlite3")
    documents_root = _document_root(tmp_path)
    (documents_root / "unreferenced.pdf").write_bytes(b"fora do snapshot")
    temporary_root = tmp_path / "private-staging"

    with build_backup_payload(
        database_path=database,
        documents_root=documents_root,
        temporary_root=temporary_root,
    ) as payload:
        assert payload.schema_revision == "20260920_0016"
        assert payload.document_count == 1
        with tarfile.open(payload.path, "r:") as archive:
            assert archive.getnames() == [
                "manifest.json",
                "db.sqlite3",
                f"documents/{_KEY}",
            ]
            manifest_bytes = archive.extractfile("manifest.json").read()
            manifest = json.loads(manifest_bytes)
            assert (
                manifest_bytes
                == json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            )
            assert manifest["document_count"] == 1
            assert (
                manifest["documents"][0]["sha256"]
                == hashlib.sha256(_CONTENT).hexdigest()
            )
            assert archive.extractfile(f"documents/{_KEY}").read() == _CONTENT
        assert list(temporary_root.iterdir())

    assert list(temporary_root.iterdir()) == []


def test_snapshot_rejects_document_divergence_and_cleans_plaintext(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path / "crm.sqlite3")
    documents_root = _document_root(tmp_path, content=b"tampered synthetic content")
    temporary_root = tmp_path / "private-staging"

    with pytest.raises(BackupSnapshotError, match="differs"):
        with build_backup_payload(
            database_path=database,
            documents_root=documents_root,
            temporary_root=temporary_root,
        ):
            pytest.fail("a divergent document must not produce a payload")

    assert list(temporary_root.iterdir()) == []


def test_snapshot_rejects_symlinked_document(tmp_path: Path) -> None:
    database = _database(tmp_path / "crm.sqlite3")
    documents_root = tmp_path / "documents"
    link = documents_root.joinpath(*_KEY.split("/"))
    link.parent.mkdir(parents=True)
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(_CONTENT)
    link.symlink_to(outside)

    with pytest.raises(BackupSnapshotError, match="reparse point"):
        with build_backup_payload(
            database_path=database,
            documents_root=documents_root,
            temporary_root=tmp_path / "private-staging",
        ):
            pytest.fail("a linked document must not enter the backup")
