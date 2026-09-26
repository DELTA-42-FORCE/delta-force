"""Construção de payload determinístico para backup local do CRM.

O snapshot usa a Online Backup API do SQLite e copia apenas arquivos referidos
pelos metadados desse snapshot. O diretório de trabalho é privado e descartado
ao sair do context manager; o payload TAR permanece disponível somente dentro
do bloco.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import tarfile
import tempfile
from collections.abc import Iterator

_STORAGE_KEY = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{32}\.(?:pdf|jpg)$")
_MAX_DOCUMENTS = 100_000
_MANIFEST_MAX_BYTES = 16 * 1024 * 1024
_COPY_CHUNK_BYTES = 1024 * 1024
_MANIFEST_NAME = "manifest.json"
_DATABASE_NAME = "db.sqlite3"


class BackupSnapshotError(Exception):
    """Snapshot inconsistente ou conteúdo local fora do contrato de backup."""


@dataclass(frozen=True, slots=True)
class BackupPayload:
    """Payload criado temporariamente para ser cifrado pelo codec #106."""

    path: Path
    schema_revision: str
    database_bytes: int
    document_count: int


@contextmanager
def build_backup_payload(
    *, database_path: Path, documents_root: Path, temporary_root: Path
) -> Iterator[BackupPayload]:
    """Gera snapshot SQLite + TAR e limpa todo plaintext temporário ao sair.

    `temporary_root` precisa ser uma pasta privada gerenciada pelo chamador.
    O chamador deve consumir o payload dentro do bloco (por exemplo, cifrando-o)
    e não deve guardar nem publicar o arquivo TAR em claro.
    """
    workspace = _create_private_workspace(temporary_root)
    payload_path = workspace / "payload.tar"
    try:
        database_snapshot = workspace / _DATABASE_NAME
        _create_database_snapshot(database_path, database_snapshot)
        schema_revision = _read_schema_revision(database_snapshot)
        documents = _copy_referenced_documents(
            database_snapshot=database_snapshot,
            documents_root=documents_root,
            workspace=workspace,
        )
        database_size, database_digest = _measure_file(database_snapshot)
        manifest = _make_manifest(
            schema_revision=schema_revision,
            database_size=database_size,
            database_digest=database_digest,
            documents=documents,
        )
        _write_payload_tar(
            destination=payload_path,
            database_snapshot=database_snapshot,
            documents=documents,
            manifest=manifest,
        )
        yield BackupPayload(
            path=payload_path,
            schema_revision=schema_revision,
            database_bytes=database_size,
            document_count=len(documents),
        )
    finally:
        try:
            shutil.rmtree(workspace)
        except OSError:
            raise BackupSnapshotError(
                "temporary backup plaintext could not be removed"
            ) from None


def _create_private_workspace(temporary_root: Path) -> Path:
    if _has_reparse_ancestor(temporary_root):
        raise BackupSnapshotError("backup staging directory is unsafe")
    temporary_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if _has_reparse_component(temporary_root) or not temporary_root.is_dir():
        raise BackupSnapshotError("backup staging directory is unsafe")
    if os.name != "nt" and stat.S_IMODE(temporary_root.stat().st_mode) & 0o077:
        raise BackupSnapshotError("backup staging directory is not private")
    path = Path(tempfile.mkdtemp(prefix="backup-snapshot-", dir=temporary_root))
    try:
        os.chmod(path, 0o700)
    except OSError:
        # Windows ACLs inherit from the private application data directory.
        if os.name != "nt":
            shutil.rmtree(path, ignore_errors=True)
            raise BackupSnapshotError(
                "backup staging directory is not private"
            ) from None
    if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        shutil.rmtree(path, ignore_errors=True)
        raise BackupSnapshotError("backup staging directory is not private")
    return path


def _is_reparse_point(path: Path) -> bool:
    result = path.lstat()
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    attributes = getattr(result, "st_file_attributes", 0)
    return stat.S_ISLNK(result.st_mode) or bool(attributes & reparse_flag)


def _create_database_snapshot(source_path: Path, destination_path: Path) -> None:
    if _has_reparse_component(source_path) or not source_path.is_file():
        raise BackupSnapshotError("database source is not a regular file")
    try:
        with sqlite3.connect(
            _readonly_uri(source_path), uri=True, timeout=30
        ) as source:
            with sqlite3.connect(destination_path, timeout=30) as destination:
                source.backup(destination, pages=256, sleep=0.05)
    except (sqlite3.Error, OSError, ValueError):
        destination_path.unlink(missing_ok=True)
        raise BackupSnapshotError("database snapshot could not be created") from None
    _sync_file(destination_path)


def _readonly_uri(path: Path) -> str:
    return f"{path.resolve().as_uri()}?mode=ro"


def _read_schema_revision(database_path: Path) -> str:
    try:
        with sqlite3.connect(_readonly_uri(database_path), uri=True) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            foreign_key_errors = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
            rows = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchall()
    except sqlite3.Error:
        raise BackupSnapshotError("database schema revision is unavailable") from None
    if (
        integrity != ("ok",)
        or foreign_key_errors
        or len(rows) != 1
        or not isinstance(rows[0][0], str)
        or not rows[0][0]
    ):
        raise BackupSnapshotError("database schema revision is invalid")
    return rows[0][0]


@dataclass(frozen=True, slots=True)
class _Document:
    storage_key: str
    staged_path: Path
    byte_size: int
    checksum_sha256: str


def _copy_referenced_documents(
    *, database_snapshot: Path, documents_root: Path, workspace: Path
) -> list[_Document]:
    if _has_reparse_component(documents_root) or not documents_root.is_dir():
        raise BackupSnapshotError("document storage root is unsafe")
    try:
        with sqlite3.connect(_readonly_uri(database_snapshot), uri=True) as connection:
            rows = connection.execute(
                "SELECT storage_key, byte_size, checksum_sha256 "
                "FROM documents ORDER BY storage_key"
            ).fetchall()
    except sqlite3.Error:
        raise BackupSnapshotError("document references could not be read") from None
    if len(rows) > _MAX_DOCUMENTS:
        raise BackupSnapshotError("backup contains too many documents")

    staged_root = workspace / "documents"
    staged_root.mkdir(mode=0o700)
    documents: list[_Document] = []
    seen: set[str] = set()
    for storage_key, expected_size, expected_digest in rows:
        if (
            not isinstance(storage_key, str)
            or not _STORAGE_KEY.fullmatch(storage_key)
            or storage_key in seen
            or not isinstance(expected_size, int)
            or expected_size <= 0
            or not isinstance(expected_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_digest)
        ):
            raise BackupSnapshotError("document metadata is invalid")
        seen.add(storage_key)
        source = documents_root.joinpath(*storage_key.split("/"))
        _assert_regular_path_under_root(source, documents_root)
        staged = staged_root.joinpath(*storage_key.split("/"))
        staged.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        size, digest = _copy_and_measure(source, staged)
        if size != expected_size or digest != expected_digest:
            raise BackupSnapshotError("document content differs from snapshot metadata")
        documents.append(_Document(storage_key, staged, size, digest))
    return documents


def _assert_regular_path_under_root(path: Path, root: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise BackupSnapshotError("document path escaped its storage root") from None
    current = root
    for part in relative.parts:
        current = current / part
        if _is_reparse_point(current):
            raise BackupSnapshotError("document path contains a reparse point")
    if not path.is_file():
        raise BackupSnapshotError("document is not a regular file")


def _has_reparse_component(path: Path) -> bool:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            if _is_reparse_point(current):
                return True
        except OSError:
            return True
    return False


def _has_reparse_ancestor(path: Path) -> bool:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            result = current.lstat()
        except FileNotFoundError:
            return False
        except OSError:
            return True
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (
            stat.S_ISLNK(result.st_mode)
            or getattr(result, "st_file_attributes", 0) & reparse_flag
        ):
            return True
    return False


def _copy_and_measure(source: Path, destination: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    output_flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    output_descriptor = os.open(destination, output_flags, 0o600)
    input_flags = (
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    )
    try:
        try:
            input_descriptor = os.open(source, input_flags)
        except OSError:
            os.close(output_descriptor)
            raise
        with (
            os.fdopen(input_descriptor, "rb") as input_file,
            os.fdopen(output_descriptor, "wb") as output,
        ):
            source_stat = os.fstat(input_file.fileno())
            if not stat.S_ISREG(source_stat.st_mode):
                raise BackupSnapshotError("document is not a regular file")
            while chunk := input_file.read(_COPY_CHUNK_BYTES):
                output.write(chunk)
                digest.update(chunk)
                size += len(chunk)
            output.flush()
            os.fsync(output.fileno())
            if os.fstat(input_file.fileno()).st_size != size:
                raise BackupSnapshotError("document changed during snapshot")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return size, digest.hexdigest()


def _measure_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(_COPY_CHUNK_BYTES):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def _make_manifest(
    *,
    schema_revision: str,
    database_size: int,
    database_digest: str,
    documents: list[_Document],
) -> bytes:
    document_entries = [
        {
            "path": f"documents/{item.storage_key}",
            "storage_key": item.storage_key,
            "size": item.byte_size,
            "sha256": item.checksum_sha256,
        }
        for item in documents
    ]
    value = {
        "format_version": 1,
        "schema_revision": schema_revision,
        "database": {
            "path": _DATABASE_NAME,
            "size": database_size,
            "sha256": database_digest,
        },
        "document_count": len(documents),
        "documents": document_entries,
    }
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > _MANIFEST_MAX_BYTES:
        raise BackupSnapshotError("backup manifest is too large")
    return encoded


def _write_payload_tar(
    *,
    destination: Path,
    database_snapshot: Path,
    documents: list[_Document],
    manifest: bytes,
) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    descriptor = os.open(destination, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            with tarfile.open(
                fileobj=output, mode="w|", format=tarfile.USTAR_FORMAT
            ) as archive:
                _add_bytes(archive, _MANIFEST_NAME, manifest)
                _add_file(archive, _DATABASE_NAME, database_snapshot)
                for document in documents:
                    _add_file(
                        archive,
                        f"documents/{document.storage_key}",
                        document.staged_path,
                    )
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def _add_bytes(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    info = _tar_info(name, len(content))
    import io

    archive.addfile(info, io.BytesIO(content))


def _add_file(archive: tarfile.TarFile, name: str, path: Path) -> None:
    info = _tar_info(name, path.stat().st_size)
    with path.open("rb") as source:
        archive.addfile(info, source)


def _tar_info(name: str, size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = 0o600
    info.type = tarfile.REGTYPE
    return info


def _sync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())
