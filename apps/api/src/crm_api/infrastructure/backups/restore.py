"""Validação e materialização isolada de uma geração de backup.

Nenhum arquivo em uso pelo aplicativo é alterado. A geração candidata vive em
staging privado e é descartada quando o chamador sai do context manager; a
ativação recuperável pertence à etapa #111.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import sys
import tarfile
import tempfile
from typing import BinaryIO

from alembic.config import Config
from alembic.script import ScriptDirectory

from crm_api.core.config import REPOSITORY_ROOT
from crm_api.infrastructure.backups.container import (
    BackupContainerError,
    BackupHeader,
    decrypt_payload,
    read_backup_header,
)

_STORAGE_KEY = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{32}\.(?:pdf|jpg)$")
_MAX_DOCUMENTS = 100_000
_MAX_MANIFEST_BYTES = 16 * 1024 * 1024
_CHUNK_BYTES = 1024 * 1024
_FREE_SPACE_MARGIN_BYTES = 64 * 1024 * 1024


class InvalidRestoreBackupError(Exception):
    """Entrada inválida ou incapaz de formar uma geração recuperável."""


class InsufficientRestoreSpaceError(Exception):
    """Espaço local insuficiente para validar o backup sem tocar nos dados ativos."""


class _InvalidPayload(Exception):
    """Erro interno de validação convertido para uma resposta pública sanitizada."""


class _InsufficientSpace(Exception):
    """Erro interno de capacidade convertido para a exceção pública específica."""


class RestoreCandidate:
    """Geração completa ainda inativa, válida somente dentro do context manager."""

    __slots__ = ("root", "database_path", "documents_root", "schema_revision")

    def __init__(self, *, root: Path, schema_revision: str) -> None:
        self.root = root
        self.database_path = root / "db.sqlite3"
        self.documents_root = root / "documents"
        self.schema_revision = schema_revision


@contextmanager
def stage_backup_restore(
    *, source_path: Path, passphrase: str, temporary_root: Path
) -> Iterator[RestoreCandidate]:
    """Autentica, valida e materializa backup sem substituir o estado ativo.

    O chamador deve concluir qualquer validação/ativação dependente enquanto o
    bloco está aberto. O payload TAR e a geração candidata são removidos ao sair
    do bloco em sucesso ou falha.
    """
    workspace = _create_private_workspace(temporary_root)
    try:
        header = _inspect_source_and_space(source_path, workspace)
        encrypted_payload = workspace / "payload.tar"
        try:
            decrypted_header = decrypt_payload(
                source_path=source_path,
                destination_path=encrypted_payload,
                passphrase=passphrase,
            )
        except (BackupContainerError, OSError, ValueError):
            raise InvalidRestoreBackupError(
                "backup is invalid or could not be restored"
            ) from None
        if decrypted_header != header:
            raise InvalidRestoreBackupError(
                "backup is invalid or could not be restored"
            )
        candidate_root = workspace / "candidate"
        candidate_root.mkdir(mode=0o700)
        try:
            schema_revision = _materialize_payload(
                payload_path=encrypted_payload,
                candidate_root=candidate_root,
                header=header,
            )
        except _InsufficientSpace:
            raise InsufficientRestoreSpaceError(
                "there is not enough free space to validate this backup"
            ) from None
        except (_InvalidPayload, OSError, sqlite3.Error, tarfile.TarError, ValueError):
            raise InvalidRestoreBackupError(
                "backup is invalid or could not be restored"
            ) from None
        yield RestoreCandidate(root=candidate_root, schema_revision=schema_revision)
    finally:
        try:
            shutil.rmtree(workspace)
        except OSError:
            raise InvalidRestoreBackupError(
                "temporary restore data could not be removed"
            ) from None


def _reparse_flag() -> int:
    return getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _is_reparse_point(path: Path) -> bool:
    result = path.lstat()
    return stat.S_ISLNK(result.st_mode) or bool(
        getattr(result, "st_file_attributes", 0) & _reparse_flag()
    )


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
        if (
            stat.S_ISLNK(result.st_mode)
            or getattr(result, "st_file_attributes", 0) & _reparse_flag()
        ):
            return True
    return False


def _create_private_workspace(temporary_root: Path) -> Path:
    if _has_reparse_ancestor(temporary_root):
        raise InvalidRestoreBackupError("restore staging directory is unsafe")
    temporary_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if _has_reparse_component(temporary_root) or not temporary_root.is_dir():
        raise InvalidRestoreBackupError("restore staging directory is unsafe")
    if os.name != "nt" and stat.S_IMODE(temporary_root.stat().st_mode) & 0o077:
        raise InvalidRestoreBackupError("restore staging directory is not private")
    workspace = Path(tempfile.mkdtemp(prefix="backup-restore-", dir=temporary_root))
    try:
        os.chmod(workspace, 0o700)
    except OSError:
        # Windows ACLs inherit from the private application data directory.
        if os.name != "nt":
            shutil.rmtree(workspace, ignore_errors=True)
            raise InvalidRestoreBackupError(
                "restore staging directory is not private"
            ) from None
    if os.name != "nt" and stat.S_IMODE(workspace.stat().st_mode) & 0o077:
        shutil.rmtree(workspace, ignore_errors=True)
        raise InvalidRestoreBackupError("restore staging directory is not private")
    return workspace


def _inspect_source_and_space(source_path: Path, workspace: Path) -> BackupHeader:
    try:
        if _has_reparse_component(source_path) or not source_path.is_file():
            raise _InvalidPayload
        with source_path.open("rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise _InvalidPayload
        header = read_backup_header(source_path)
    except (BackupContainerError, OSError, ValueError, _InvalidPayload):
        raise InvalidRestoreBackupError(
            "backup is invalid or could not be restored"
        ) from None

    required_space = 2 * header.payload_bytes + _FREE_SPACE_MARGIN_BYTES
    try:
        free_space = shutil.disk_usage(workspace).free
    except OSError:
        raise InvalidRestoreBackupError(
            "restore staging volume is unavailable"
        ) from None
    if free_space < required_space:
        raise InsufficientRestoreSpaceError(
            "there is not enough free space to validate this backup"
        )
    return header


def _materialize_payload(
    *, payload_path: Path, candidate_root: Path, header: BackupHeader
) -> str:
    documents_root = candidate_root / "documents"
    documents_root.mkdir(mode=0o700)
    try:
        with (
            tarfile.open(payload_path, mode="r:") as archive,
            payload_path.open("rb") as raw_archive,
        ):
            expected_offset = 0
            manifest_member = archive.next()
            if manifest_member is None or manifest_member.name != "manifest.json":
                raise _InvalidPayload
            expected_offset = _validate_member_layout(
                raw_archive, manifest_member, expected_offset
            )
            manifest_bytes = _read_member_bytes(
                archive, manifest_member, maximum=_MAX_MANIFEST_BYTES
            )
            manifest = _parse_manifest(manifest_bytes, header=header)
            _validate_tar_size(payload_path, manifest)
            database_entry = manifest["database"]
            database_member = archive.next()
            if database_member is None or database_member.name != "db.sqlite3":
                raise _InvalidPayload
            expected_offset = _validate_member_layout(
                raw_archive, database_member, expected_offset
            )
            _materialize_member(
                archive,
                database_member,
                destination=candidate_root / "db.sqlite3",
                expected_size=database_entry["size"],
                expected_digest=database_entry["sha256"],
            )

            expected_documents = manifest["documents"]
            for item in expected_documents:
                member = archive.next()
                expected_name = f"documents/{item['storage_key']}"
                if member is None or member.name != expected_name:
                    raise _InvalidPayload
                expected_offset = _validate_member_layout(
                    raw_archive, member, expected_offset
                )
                destination = documents_root.joinpath(*item["storage_key"].split("/"))
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                _materialize_member(
                    archive,
                    member,
                    destination=destination,
                    expected_size=item["size"],
                    expected_digest=item["sha256"],
                )
            if archive.next() is not None:
                raise _InvalidPayload
            raw_archive.seek(expected_offset)
            if any(raw_archive.read()):
                raise _InvalidPayload
    except (tarfile.TarError, OSError, ValueError, KeyError, TypeError):
        raise _InvalidPayload from None

    schema_revision = manifest["schema_revision"]
    _validate_database(
        database_path=candidate_root / "db.sqlite3",
        documents=manifest["documents"],
        schema_revision=schema_revision,
    )
    return schema_revision


def _read_member_bytes(
    archive: tarfile.TarFile, member: tarfile.TarInfo, *, maximum: int
) -> bytes:
    _assert_regular_member(member)
    if member.size > maximum:
        raise _InvalidPayload
    stream = archive.extractfile(member)
    if stream is None:
        raise _InvalidPayload
    content = stream.read(maximum + 1)
    if len(content) != member.size or len(content) > maximum:
        raise _InvalidPayload
    return content


def _parse_manifest(content: bytes, *, header: BackupHeader) -> dict[str, object]:
    try:
        value = json.loads(content)
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        raise _InvalidPayload from None
    if content != canonical or not isinstance(value, dict):
        raise _InvalidPayload
    if set(value) != {
        "format_version",
        "schema_revision",
        "database",
        "document_count",
        "documents",
    }:
        raise _InvalidPayload
    if (
        type(value["format_version"]) is not int
        or value["format_version"] != 1
        or value["schema_revision"] != header.schema_revision
        or not isinstance(value["schema_revision"], str)
    ):
        raise _InvalidPayload
    database = value["database"]
    documents = value["documents"]
    if (
        not isinstance(database, dict)
        or set(database) != {"path", "size", "sha256"}
        or database.get("path") != "db.sqlite3"
        or not _valid_size(database.get("size"))
        or not _valid_digest(database.get("sha256"))
        or not isinstance(documents, list)
        or len(documents) > _MAX_DOCUMENTS
        or type(value["document_count"]) is not int
        or value["document_count"] != len(documents)
    ):
        raise _InvalidPayload
    previous_key = ""
    for item in documents:
        if (
            not isinstance(item, dict)
            or set(item) != {"path", "storage_key", "size", "sha256"}
            or not isinstance(item.get("storage_key"), str)
            or not _STORAGE_KEY.fullmatch(item["storage_key"])
            or item.get("path") != f"documents/{item['storage_key']}"
            or not _valid_size(item.get("size"))
            or item["size"] == 0
            or not _valid_digest(item.get("sha256"))
            or item["storage_key"] <= previous_key
        ):
            raise _InvalidPayload
        previous_key = item["storage_key"]
    return value


def _valid_size(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _valid_digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _assert_regular_member(member: tarfile.TarInfo) -> None:
    if (
        member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE)
        or member.linkname
        or member.pax_headers
        or member.uid != 0
        or member.gid != 0
        or member.uname
        or member.gname
        or member.mode != 0o600
        or member.mtime != 0
        or member.devmajor != 0
        or member.devminor != 0
    ):
        raise _InvalidPayload


def _validate_tar_size(payload_path: Path, manifest: dict[str, object]) -> None:
    database = manifest["database"]
    documents = manifest["documents"]
    assert isinstance(database, dict) and isinstance(documents, list)
    member_sizes = [
        len(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ),
        database["size"],
        *(item["size"] for item in documents),
    ]
    member_region = sum(512 + ((size + 511) // 512) * 512 for size in member_sizes)
    expected_size = ((member_region + 1024 + 10239) // 10240) * 10240
    if payload_path.stat().st_size != expected_size:
        raise _InvalidPayload


def _validate_member_layout(
    raw_archive: BinaryIO, member: tarfile.TarInfo, expected_offset: int
) -> int:
    """Rejeita cabeçalhos ocultos e padding não canônico entre membros."""
    data_offset = expected_offset + 512
    if member.offset != expected_offset or member.offset_data != data_offset:
        raise _InvalidPayload
    padding_size = (-member.size) % 512
    raw_archive.seek(data_offset + member.size)
    if raw_archive.read(padding_size) != bytes(padding_size):
        raise _InvalidPayload
    return data_offset + member.size + padding_size


def _materialize_member(
    archive: tarfile.TarFile,
    member: tarfile.TarInfo,
    *,
    destination: Path,
    expected_size: int,
    expected_digest: str,
) -> None:
    _assert_regular_member(member)
    if member.size != expected_size:
        raise _InvalidPayload
    stream = archive.extractfile(member)
    if stream is None:
        raise _InvalidPayload
    digest = hashlib.sha256()
    written = 0
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    descriptor = os.open(destination, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            while chunk := stream.read(_CHUNK_BYTES):
                output.write(chunk)
                digest.update(chunk)
                written += len(chunk)
            output.flush()
            os.fsync(output.fileno())
    except OSError as error:
        destination.unlink(missing_ok=True)
        if error.errno == errno.ENOSPC or getattr(error, "winerror", None) == 112:
            raise _InsufficientSpace from None
        raise
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    if written != expected_size or digest.hexdigest() != expected_digest:
        destination.unlink(missing_ok=True)
        raise _InvalidPayload


def _validate_database(
    *, database_path: Path, documents: list[dict[str, object]], schema_revision: str
) -> None:
    try:
        with sqlite3.connect(_readonly_uri(database_path), uri=True) as db:
            integrity = db.execute("PRAGMA integrity_check").fetchone()
            foreign_key_errors = db.execute("PRAGMA foreign_key_check").fetchall()
            revision_rows = db.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchall()
            document_rows = db.execute(
                "SELECT storage_key, byte_size, checksum_sha256 FROM documents "
                "ORDER BY storage_key"
            ).fetchall()
    except sqlite3.Error:
        raise _InvalidPayload from None
    if integrity != ("ok",) or foreign_key_errors:
        raise _InvalidPayload
    if revision_rows != [(schema_revision,)]:
        raise _InvalidPayload
    expected_rows = [
        (item["storage_key"], item["size"], item["sha256"]) for item in documents
    ]
    if document_rows != expected_rows:
        raise _InvalidPayload
    _validate_known_alembic_revision(database_path, schema_revision)


def _validate_known_alembic_revision(database_path: Path, revision: str) -> None:
    api_root = _api_root()
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    try:
        script = ScriptDirectory.from_config(config)
        if script.get_revision(revision) is None:
            raise _InvalidPayload
        with sqlite3.connect(_readonly_uri(database_path), uri=True) as db:
            current = db.execute("SELECT version_num FROM alembic_version").fetchone()
        if current != (revision,):
            raise _InvalidPayload
    except Exception:
        raise _InvalidPayload from None


def _readonly_uri(path: Path) -> str:
    return f"{path.resolve().as_uri()}?mode=ro"


def _api_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return REPOSITORY_ROOT / "apps" / "api"
