"""Snapshot SQLite/documentos e restauração validada do backup cifrado."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import tarfile
from typing import BinaryIO
from uuid import uuid4

from crm_api.domain.backups.entities import (
    BackupCreationResult,
    RestoreStagingResult,
)
from crm_api.infrastructure.backups.container import (
    MAX_PAYLOAD_BYTES,
    BackupHeader,
    decrypt_payload,
    encrypt_payload,
)
from crm_api.infrastructure.backups.media import BackupMediaPolicy

BACKUP_EXTENSION = ".dfcrmbak"
DATABASE_ARCHIVE_NAME = "db.sqlite3"
DOCUMENTS_ARCHIVE_PREFIX = "documents/"
MANIFEST_ARCHIVE_NAME = "manifest.json"
ACTIVE_DATABASE_NAME = "crm.sqlite3"
ACTIVE_DOCUMENTS_NAME = "documents"
RESTORE_MARKER_NAME = "restore.pending"
FORMAT_VERSION = 1
COPY_CHUNK_BYTES = 1024 * 1024
FREE_SPACE_MARGIN_BYTES = 64 * 1024 * 1024
MAX_DOCUMENT_COUNT = 100_000
MAX_MANIFEST_BYTES = 16 * 1024 * 1024

_STORAGE_KEY_PATTERN = re.compile(
    r"^[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{32}\.(?:pdf|jpg)$"
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CANDIDATE_PATTERN = re.compile(r"^restore-candidate-[0-9a-f]{32}$")
_BACKUP_FILENAME_PATTERN = re.compile(
    r"^delta-force-crm-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}\.dfcrmbak$"
)
_ROLLBACK_DIRECTORY_NAME = "restore-rollback"


class BackupServiceError(Exception):
    pass


class BackupSourceIntegrityError(BackupServiceError):
    pass


class BackupInsufficientSpaceError(BackupServiceError):
    pass


class RestoreRequiresEmptyInstallationError(BackupServiceError):
    pass


class RestoreAlreadyPendingError(BackupServiceError):
    pass


@dataclass(frozen=True, slots=True)
class _ManifestFile:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class _BackupManifest:
    created_at: str
    schema_revision: str
    database: _ManifestFile
    documents: tuple[_ManifestFile, ...]
    total_plaintext_bytes: int


@dataclass(frozen=True, slots=True)
class EncryptedBackupService:
    data_root: Path
    database_path: Path
    documents_root: Path
    media_policy: BackupMediaPolicy
    app_version: str = "0.1.0"

    def __post_init__(self) -> None:
        if self.database_path.resolve().parent != self.data_root.resolve():
            raise ValueError("backup database must be inside the private data root")
        if (
            self.documents_root.resolve()
            != (self.data_root / ACTIVE_DOCUMENTS_NAME).resolve()
        ):
            raise ValueError("backup documents must use the private data root")

    def create_backup(
        self,
        *,
        destination_directory: str,
        passphrase: str,
        now: datetime | None = None,
    ) -> BackupCreationResult:
        created_at = _as_utc(now or datetime.now(UTC))
        media = self.media_policy.validate_directory(destination_directory)
        work_root = self._new_private_directory(prefix=".backup-work-")
        partial_path: Path | None = None
        try:
            snapshot_path = work_root / DATABASE_ARCHIVE_NAME
            _snapshot_sqlite(self.database_path, snapshot_path)
            schema_revision = _database_revision(snapshot_path)
            expected_documents = _database_documents(snapshot_path)
            if len(expected_documents) > MAX_DOCUMENT_COUNT:
                raise BackupSourceIntegrityError("too many documents for one backup")
            staged_documents = work_root / ACTIVE_DOCUMENTS_NAME
            staged_documents.mkdir(mode=0o700)
            document_entries = tuple(
                self._stage_document(
                    storage_key=storage_key,
                    expected_size=expected_size,
                    expected_sha256=expected_sha256,
                    destination_root=staged_documents,
                )
                for storage_key, expected_size, expected_sha256 in expected_documents
            )
            database_entry = _manifest_file(
                snapshot_path, archive_path=DATABASE_ARCHIVE_NAME
            )
            manifest = _BackupManifest(
                created_at=_format_timestamp(created_at),
                schema_revision=schema_revision,
                database=database_entry,
                documents=document_entries,
                total_plaintext_bytes=database_entry.size
                + sum(item.size for item in document_entries),
            )
            manifest_path = work_root / MANIFEST_ARCHIVE_NAME
            manifest_path.write_bytes(_manifest_bytes(manifest))
            payload_path = work_root / "payload.tar"
            _write_tar(
                payload_path=payload_path,
                manifest_path=manifest_path,
                database_path=snapshot_path,
                documents_root=staged_documents,
                documents=document_entries,
            )
            self._require_free_space(
                media.directory,
                required_bytes=payload_path.stat().st_size + FREE_SPACE_MARGIN_BYTES,
            )
            basename = (
                f"delta-force-crm-{created_at:%Y%m%dT%H%M%SZ}-"
                f"{uuid4().hex[:8]}{BACKUP_EXTENSION}"
            )
            final_path = media.directory / basename
            partial_path = media.directory / f".{basename}.{uuid4().hex}.partial"
            encrypt_payload(
                payload_path=payload_path,
                destination_path=partial_path,
                passphrase=passphrase,
                app_version=self.app_version,
                created_at=manifest.created_at,
                schema_revision=schema_revision,
            )
            self.media_policy.revalidate(media)
            if final_path.exists():
                raise BackupServiceError("backup destination already exists")
            os.rename(partial_path, final_path)
            partial_path = None
            _sync_directory(media.directory)
            return BackupCreationResult(
                filename=basename,
                created_at=created_at,
                byte_size=final_path.stat().st_size,
                document_count=len(document_entries),
            )
        finally:
            if partial_path is not None:
                partial_path.unlink(missing_ok=True)
            _safe_remove_tree(self.data_root, work_root)

    def stage_restore(
        self, *, source_file: str, passphrase: str
    ) -> RestoreStagingResult:
        if not is_empty_installation(self.database_path, self.documents_root):
            raise RestoreRequiresEmptyInstallationError(
                "restore requires an empty installation"
            )
        marker_path = self.data_root / RESTORE_MARKER_NAME
        if marker_path.exists():
            raise RestoreAlreadyPendingError("another restore is already pending")
        source_path, media = self.media_policy.validate_source_file(source_file)
        if source_path.suffix.lower() != BACKUP_EXTENSION:
            raise BackupServiceError("backup file extension is invalid")
        work_root = self._new_private_directory(prefix=".restore-work-")
        candidate_root = self._new_private_directory(prefix="restore-candidate-")
        marker_created = False
        try:
            header = _read_and_check_restore_capacity(
                source_path=source_path, destination=self.data_root
            )
            expected_revision = _database_revision(self.database_path)
            if header.schema_revision != expected_revision:
                raise BackupServiceError("backup schema is incompatible")
            payload_path = work_root / "payload.tar"
            decrypted_header = decrypt_payload(
                source_path=source_path,
                destination_path=payload_path,
                passphrase=passphrase,
            )
            if decrypted_header != header:
                raise BackupServiceError("backup header changed during restore")
            manifest = _extract_and_validate_tar(
                payload_path=payload_path,
                candidate_root=candidate_root,
                expected_header=header,
            )
            candidate_database = candidate_root / ACTIVE_DATABASE_NAME
            _validate_sqlite(candidate_database, expected_revision=expected_revision)
            _validate_database_documents(
                candidate_database,
                candidate_root / ACTIVE_DOCUMENTS_NAME,
                manifest.documents,
            )
            self.media_policy.revalidate(media)
            _write_restore_marker(marker_path, candidate_root.name)
            marker_created = True
            return RestoreStagingResult(
                created_at=manifest.created_at,
                document_count=len(manifest.documents),
            )
        finally:
            _safe_remove_tree(self.data_root, work_root)
            if not marker_created:
                _safe_remove_tree(self.data_root, candidate_root)

    def discard_backup(self, *, destination_directory: str, filename: str) -> None:
        """Compensa uma publicação cuja auditoria transacional falhou."""
        if not _BACKUP_FILENAME_PATTERN.fullmatch(filename):
            raise BackupServiceError("refusing to discard an unexpected backup")
        media = self.media_policy.validate_directory(destination_directory)
        target = media.directory / filename
        try:
            metadata = target.lstat()
        except FileNotFoundError:
            return
        _reject_link_or_reparse(metadata, message="backup file is not plain")
        if not stat.S_ISREG(metadata.st_mode):
            raise BackupServiceError("backup file is not regular")
        self.media_policy.revalidate(media)
        target.unlink()
        _sync_directory(media.directory)

    def _stage_document(
        self,
        *,
        storage_key: str,
        expected_size: int,
        expected_sha256: str,
        destination_root: Path,
    ) -> _ManifestFile:
        if not _STORAGE_KEY_PATTERN.fullmatch(storage_key):
            raise BackupSourceIntegrityError("database contains an invalid storage key")
        source = self.documents_root.joinpath(*storage_key.split("/"))
        _require_plain_regular_file(source, root=self.documents_root)
        destination = destination_root.joinpath(*storage_key.split("/"))
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        size, digest = _copy_exclusively(source, destination)
        if size != expected_size or digest != expected_sha256:
            raise BackupSourceIntegrityError(
                "stored document does not match its database metadata"
            )
        return _ManifestFile(
            path=f"{DOCUMENTS_ARCHIVE_PREFIX}{storage_key}",
            size=size,
            sha256=digest,
        )

    def _new_private_directory(self, *, prefix: str) -> Path:
        self.data_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        candidate = self.data_root / f"{prefix}{uuid4().hex}"
        candidate.mkdir(mode=0o700)
        return candidate

    @staticmethod
    def _require_free_space(destination: Path, *, required_bytes: int) -> None:
        if shutil.disk_usage(destination).free < required_bytes:
            raise BackupInsufficientSpaceError(
                "destination does not have enough free space"
            )


def is_empty_installation(database_path: Path, documents_root: Path) -> bool:
    """A restauração nunca substitui uma instalação que já contenha dono/dados."""
    if not database_path.exists():
        return True
    with closing(sqlite3.connect(database_path)) as connection:
        has_data = connection.execute(
            "SELECT EXISTS(SELECT 1 FROM users) "
            "OR EXISTS(SELECT 1 FROM client_folders) "
            "OR EXISTS(SELECT 1 FROM documents) "
            "OR EXISTS(SELECT 1 FROM message_templates)"
        ).fetchone()
        if has_data != (0,):
            return False
    if not documents_root.exists():
        return True
    if any(item.name != "_incoming" for item in documents_root.iterdir()):
        return False
    incoming = documents_root / "_incoming"
    return not incoming.exists() or not any(incoming.iterdir())


def activate_pending_restore(data_root: Path) -> bool:
    """Ativa a restauração antes de o engine SQLite abrir qualquer arquivo."""
    data_root = data_root.resolve()
    marker_path = data_root / RESTORE_MARKER_NAME
    if not marker_path.exists():
        return False
    rollback_root = data_root / _ROLLBACK_DIRECTORY_NAME
    active_database = data_root / ACTIVE_DATABASE_NAME
    active_documents = data_root / ACTIVE_DOCUMENTS_NAME

    if _path_exists_without_following(rollback_root):
        _rollback_activation(
            data_root=data_root,
            rollback_root=rollback_root,
            active_database=active_database,
            active_documents=active_documents,
        )
        _remove_restore_candidates(data_root)
        marker_path.unlink(missing_ok=True)
        raise BackupServiceError("an interrupted restore was rolled back")
    try:
        candidate_root = _candidate_from_marker(data_root, marker_path)
    except BaseException:
        _remove_restore_candidates(data_root)
        marker_path.unlink(missing_ok=True)
        raise
    if not is_empty_installation(active_database, active_documents):
        _safe_remove_tree(data_root, candidate_root)
        marker_path.unlink(missing_ok=True)
        raise RestoreRequiresEmptyInstallationError(
            "restore refused because the installation is no longer empty"
        )

    candidate_database = candidate_root / ACTIVE_DATABASE_NAME
    candidate_documents = candidate_root / ACTIVE_DOCUMENTS_NAME
    try:
        _require_plain_regular_file(candidate_database, root=candidate_root)
        _require_plain_directory(
            candidate_documents, message="restore candidate documents are invalid"
        )
        expected_revision = _database_revision(candidate_database)
        _validate_sqlite(candidate_database, expected_revision=expected_revision)
    except BaseException:
        _safe_remove_tree(data_root, candidate_root)
        marker_path.unlink(missing_ok=True)
        raise
    rollback_root.mkdir(mode=0o700)
    try:
        if active_database.exists():
            os.rename(active_database, rollback_root / ACTIVE_DATABASE_NAME)
        if active_documents.exists():
            os.rename(active_documents, rollback_root / ACTIVE_DOCUMENTS_NAME)
        os.rename(candidate_database, active_database)
        os.rename(candidate_documents, active_documents)
        _validate_sqlite(active_database, expected_revision=expected_revision)
        _record_restore_audit(active_database)
    except BaseException:
        _rollback_activation(
            data_root=data_root,
            rollback_root=rollback_root,
            active_database=active_database,
            active_documents=active_documents,
        )
        _safe_remove_tree(data_root, candidate_root)
        marker_path.unlink(missing_ok=True)
        raise

    _safe_remove_tree(data_root, rollback_root)
    _safe_remove_tree(data_root, candidate_root)
    marker_path.unlink(missing_ok=True)
    _sync_directory(data_root)
    return True


def _snapshot_sqlite(source_path: Path, destination_path: Path) -> None:
    if not source_path.exists() or not source_path.is_file():
        raise BackupSourceIntegrityError("SQLite database is unavailable")
    source_uri = f"file:{source_path.resolve().as_posix()}?mode=ro"
    with (
        closing(sqlite3.connect(source_uri, uri=True)) as source,
        closing(sqlite3.connect(destination_path)) as destination,
    ):
        source.backup(destination)
        destination.execute("PRAGMA journal_mode=DELETE")
        destination.commit()
    _flush_file(destination_path)
    _validate_sqlite(
        destination_path, expected_revision=_database_revision(source_path)
    )


def _database_revision(database_path: Path) -> str:
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    if row is None or len(row) != 1 or not isinstance(row[0], str) or not row[0]:
        raise BackupSourceIntegrityError("database schema revision is unavailable")
    return row[0]


def _database_documents(database_path: Path) -> tuple[tuple[str, int, str], ...]:
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            "SELECT storage_key, byte_size, checksum_sha256 "
            "FROM documents ORDER BY storage_key"
        ).fetchall()
    result = []
    for storage_key, byte_size, checksum in rows:
        if (
            not isinstance(storage_key, str)
            or type(byte_size) is not int
            or byte_size <= 0
            or not isinstance(checksum, str)
            or not _SHA256_PATTERN.fullmatch(checksum)
        ):
            raise BackupSourceIntegrityError(
                "database contains invalid document metadata"
            )
        result.append((storage_key, byte_size, checksum))
    return tuple(result)


def _validate_sqlite(database_path: Path, *, expected_revision: str) -> None:
    with closing(sqlite3.connect(database_path)) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        revision = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
    if integrity != ("ok",) or foreign_keys or revision != (expected_revision,):
        raise BackupSourceIntegrityError("backup database failed integrity checks")


def _record_restore_audit(database_path: Path) -> None:
    """Registra a ativação anônima antes de liberar o banco restaurado."""
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(
            "INSERT INTO audit_events "
            "(id, occurred_at, actor_kind, actor_user_id, action, "
            "resource_type, resource_id, result, context) "
            "VALUES (?, ?, 'anonymous', NULL, 'backup.restore_applied', "
            "'backup', NULL, 'success', '{}')",
            (uuid4().hex, datetime.now(UTC).isoformat()),
        )
        connection.commit()
    _flush_file(database_path)


def _manifest_file(path: Path, *, archive_path: str) -> _ManifestFile:
    size, digest = _hash_file(path)
    return _ManifestFile(path=archive_path, size=size, sha256=digest)


def _manifest_bytes(manifest: _BackupManifest) -> bytes:
    data = {
        "created_at": manifest.created_at,
        "database": _manifest_file_data(manifest.database),
        "document_count": len(manifest.documents),
        "documents": [_manifest_file_data(item) for item in manifest.documents],
        "format_version": FORMAT_VERSION,
        "schema_revision": manifest.schema_revision,
        "total_plaintext_bytes": manifest.total_plaintext_bytes,
    }
    encoded = json.dumps(
        data,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise BackupServiceError("backup manifest is too large")
    return encoded


def _manifest_file_data(item: _ManifestFile) -> dict[str, str | int]:
    return {"path": item.path, "sha256": item.sha256, "size": item.size}


def _write_tar(
    *,
    payload_path: Path,
    manifest_path: Path,
    database_path: Path,
    documents_root: Path,
    documents: tuple[_ManifestFile, ...],
) -> None:
    with tarfile.open(payload_path, mode="w", format=tarfile.PAX_FORMAT) as archive:
        _add_tar_file(archive, manifest_path, MANIFEST_ARCHIVE_NAME)
        _add_tar_file(archive, database_path, DATABASE_ARCHIVE_NAME)
        for entry in documents:
            storage_key = entry.path.removeprefix(DOCUMENTS_ARCHIVE_PREFIX)
            _add_tar_file(
                archive,
                documents_root.joinpath(*storage_key.split("/")),
                entry.path,
            )
    _flush_file(payload_path)


def _add_tar_file(archive: tarfile.TarFile, source: Path, name: str) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = source.stat().st_size
    info.mode = 0o600
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    with source.open("rb") as handle:
        archive.addfile(info, handle)


def _read_and_check_restore_capacity(
    *, source_path: Path, destination: Path
) -> BackupHeader:
    from crm_api.infrastructure.backups.container import read_backup_header

    header = read_backup_header(source_path)
    required = header.payload_size * 2 + FREE_SPACE_MARGIN_BYTES
    if shutil.disk_usage(destination).free < required:
        raise BackupInsufficientSpaceError(
            "installation disk does not have enough space for restore"
        )
    return header


def _extract_and_validate_tar(
    *, payload_path: Path, candidate_root: Path, expected_header: BackupHeader
) -> _BackupManifest:
    with tarfile.open(payload_path, mode="r:", errorlevel=2) as archive:
        members = []
        while member := archive.next():
            members.append(member)
            if len(members) > MAX_DOCUMENT_COUNT + 2:
                raise BackupSourceIntegrityError(
                    "backup archive entry count is invalid"
                )
        if len(members) < 2:
            raise BackupSourceIntegrityError("backup archive entry count is invalid")
        if any(not member.isreg() for member in members):
            raise BackupSourceIntegrityError("backup archive contains a non-file entry")
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise BackupSourceIntegrityError(
                "backup archive contains duplicate entries"
            )
        members_by_name = {member.name: member for member in members}
        manifest_member = members_by_name.get(MANIFEST_ARCHIVE_NAME)
        if manifest_member is None:
            raise BackupSourceIntegrityError("backup manifest is missing") from None
        if not 0 < manifest_member.size <= MAX_MANIFEST_BYTES:
            raise BackupSourceIntegrityError("backup manifest size is invalid")
        manifest_stream = archive.extractfile(manifest_member)
        if manifest_stream is None:
            raise BackupSourceIntegrityError("backup manifest is unavailable")
        manifest_raw = manifest_stream.read(MAX_MANIFEST_BYTES + 1)
        manifest = _parse_manifest(manifest_raw)
        if _manifest_bytes(manifest) != manifest_raw:
            raise BackupSourceIntegrityError("backup manifest is not canonical")
        if (
            manifest.created_at != expected_header.created_at
            or manifest.schema_revision != expected_header.schema_revision
        ):
            raise BackupSourceIntegrityError("backup header and manifest disagree")
        expected_entries = {
            MANIFEST_ARCHIVE_NAME,
            manifest.database.path,
            *(item.path for item in manifest.documents),
        }
        if set(names) != expected_entries:
            raise BackupSourceIntegrityError("backup archive entries are inconsistent")

        database_destination = candidate_root / ACTIVE_DATABASE_NAME
        _extract_verified_member(
            archive,
            members_by_name[manifest.database.path],
            database_destination,
            manifest.database,
        )
        documents_root = candidate_root / ACTIVE_DOCUMENTS_NAME
        documents_root.mkdir(mode=0o700)
        (documents_root / "_incoming").mkdir(mode=0o700)
        for entry in manifest.documents:
            storage_key = entry.path.removeprefix(DOCUMENTS_ARCHIVE_PREFIX)
            destination = documents_root.joinpath(*storage_key.split("/"))
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            _extract_verified_member(
                archive, members_by_name[entry.path], destination, entry
            )
    return manifest


def _parse_manifest(raw: bytes) -> _BackupManifest:
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BackupSourceIntegrityError("backup manifest is invalid") from None
    required = {
        "created_at",
        "database",
        "document_count",
        "documents",
        "format_version",
        "schema_revision",
        "total_plaintext_bytes",
    }
    if not isinstance(data, dict) or set(data) != required:
        raise BackupSourceIntegrityError("backup manifest fields are invalid")
    if data.get("format_version") != FORMAT_VERSION:
        raise BackupSourceIntegrityError("backup manifest version is unsupported")
    created_at = _manifest_text(data.get("created_at"), "created_at")
    schema_revision = _manifest_text(data.get("schema_revision"), "schema_revision")
    database = _parse_manifest_file(data.get("database"), expected_database=True)
    raw_documents = data.get("documents")
    if not isinstance(raw_documents, list) or len(raw_documents) > MAX_DOCUMENT_COUNT:
        raise BackupSourceIntegrityError("backup document list is invalid")
    documents = tuple(
        _parse_manifest_file(item, expected_database=False) for item in raw_documents
    )
    if len({item.path for item in documents}) != len(documents):
        raise BackupSourceIntegrityError("backup document list contains duplicates")
    document_count = data.get("document_count")
    total_bytes = data.get("total_plaintext_bytes")
    expected_total = database.size + sum(item.size for item in documents)
    if (
        type(document_count) is not int
        or document_count != len(documents)
        or type(total_bytes) is not int
        or total_bytes != expected_total
        or not 0 < total_bytes <= MAX_PAYLOAD_BYTES
    ):
        raise BackupSourceIntegrityError("backup manifest totals are invalid")
    return _BackupManifest(
        created_at=created_at,
        schema_revision=schema_revision,
        database=database,
        documents=documents,
        total_plaintext_bytes=total_bytes,
    )


def _parse_manifest_file(value: object, *, expected_database: bool) -> _ManifestFile:
    if not isinstance(value, dict) or set(value) != {"path", "size", "sha256"}:
        raise BackupSourceIntegrityError("backup manifest file entry is invalid")
    path = value.get("path")
    size = value.get("size")
    digest = value.get("sha256")
    if expected_database:
        valid_path = path == DATABASE_ARCHIVE_NAME
    else:
        valid_path = (
            isinstance(path, str)
            and path.startswith(DOCUMENTS_ARCHIVE_PREFIX)
            and _STORAGE_KEY_PATTERN.fullmatch(
                path.removeprefix(DOCUMENTS_ARCHIVE_PREFIX)
            )
        )
    if (
        not valid_path
        or type(size) is not int
        or size <= 0
        or not isinstance(digest, str)
        or not _SHA256_PATTERN.fullmatch(digest)
    ):
        raise BackupSourceIntegrityError("backup manifest file entry is invalid")
    return _ManifestFile(path=path, size=size, sha256=digest)


def _manifest_text(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 128
        or not value.isascii()
    ):
        raise BackupSourceIntegrityError(f"backup manifest {field} is invalid")
    return value


def _extract_verified_member(
    archive: tarfile.TarFile,
    member: tarfile.TarInfo,
    destination: Path,
    expected: _ManifestFile,
) -> None:
    if member.name != expected.path or member.size != expected.size:
        raise BackupSourceIntegrityError("backup archive file size is inconsistent")
    source = archive.extractfile(member)
    if source is None:
        raise BackupSourceIntegrityError("backup archive file is unavailable")
    size, digest = _copy_stream_exclusively(source, destination)
    if size != expected.size or digest != expected.sha256:
        destination.unlink(missing_ok=True)
        raise BackupSourceIntegrityError("backup archive file failed checksum")


def _validate_database_documents(
    database_path: Path,
    documents_root: Path,
    manifest_documents: tuple[_ManifestFile, ...],
) -> None:
    database_documents = _database_documents(database_path)
    expected = {
        f"{DOCUMENTS_ARCHIVE_PREFIX}{storage_key}": (size, digest)
        for storage_key, size, digest in database_documents
    }
    actual = {item.path: (item.size, item.sha256) for item in manifest_documents}
    if actual != expected:
        raise BackupSourceIntegrityError(
            "restored documents do not match database references"
        )
    for item in manifest_documents:
        storage_key = item.path.removeprefix(DOCUMENTS_ARCHIVE_PREFIX)
        _require_plain_regular_file(
            documents_root.joinpath(*storage_key.split("/")), root=documents_root
        )


def _copy_exclusively(source: Path, destination: Path) -> tuple[int, str]:
    with source.open("rb") as input_handle:
        return _copy_stream_exclusively(input_handle, destination)


def _copy_stream_exclusively(source: BinaryIO, destination: Path) -> tuple[int, str]:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    descriptor = os.open(destination, flags, 0o600)
    digest = hashlib.sha256()
    total = 0
    try:
        with os.fdopen(descriptor, "wb") as output:
            while True:
                chunk = source.read(COPY_CHUNK_BYTES)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
                total += len(chunk)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return total, digest.hexdigest()


def _hash_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        while chunk := handle.read(COPY_CHUNK_BYTES):
            digest.update(chunk)
            total += len(chunk)
    return total, digest.hexdigest()


def _require_plain_regular_file(path: Path, *, root: Path) -> None:
    _require_plain_directory(root, message="document root is invalid")
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise BackupSourceIntegrityError("document escaped the private root") from None
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise BackupSourceIntegrityError("document path is invalid")
    current = root
    for part in relative.parts:
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as error:
            raise BackupSourceIntegrityError(
                "stored document is unavailable"
            ) from error
        attributes = getattr(metadata, "st_file_attributes", 0)
        reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if stat.S_ISLNK(metadata.st_mode) or attributes & reparse_attribute:
            raise BackupSourceIntegrityError(
                "stored document path contains a link or reparse point"
            )
    if not path.is_file():
        raise BackupSourceIntegrityError("stored document is not a regular file")


def _write_restore_marker(marker_path: Path, candidate_name: str) -> None:
    if not _CANDIDATE_PATTERN.fullmatch(candidate_name):
        raise BackupServiceError("restore candidate name is invalid")
    raw = json.dumps(
        {"candidate": candidate_name, "version": FORMAT_VERSION},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    descriptor = os.open(marker_path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    _sync_directory(marker_path.parent)


def _candidate_from_marker(data_root: Path, marker_path: Path) -> Path:
    try:
        raw = marker_path.read_bytes()
        data = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise BackupServiceError("restore marker is invalid") from None
    if (
        not isinstance(data, dict)
        or set(data) != {"candidate", "version"}
        or data.get("version") != FORMAT_VERSION
        or not isinstance(data.get("candidate"), str)
        or not _CANDIDATE_PATTERN.fullmatch(data["candidate"])
    ):
        raise BackupServiceError("restore marker is invalid")
    candidate = _validated_direct_child(data_root, data_root / data["candidate"])
    _require_plain_directory(candidate, message="restore candidate is invalid")
    return candidate


def _remove_restore_candidates(data_root: Path) -> None:
    for candidate in data_root.iterdir():
        if _CANDIDATE_PATTERN.fullmatch(candidate.name):
            _safe_remove_tree(data_root, candidate)


def _rollback_activation(
    *,
    data_root: Path,
    rollback_root: Path,
    active_database: Path,
    active_documents: Path,
) -> None:
    rollback_root = _validated_direct_child(data_root, rollback_root)
    _require_plain_directory(rollback_root, message="restore rollback is invalid")
    rollback_database = rollback_root / ACTIVE_DATABASE_NAME
    rollback_documents = rollback_root / ACTIVE_DOCUMENTS_NAME
    if _path_exists_without_following(rollback_database):
        _require_plain_regular_file(rollback_database, root=rollback_root)
    if _path_exists_without_following(rollback_documents):
        _require_plain_directory(
            rollback_documents, message="restore rollback documents are invalid"
        )
    active_database.unlink(missing_ok=True)
    _safe_remove_tree(data_root, active_documents)
    if _path_exists_without_following(rollback_database):
        os.rename(rollback_database, active_database)
    if _path_exists_without_following(rollback_documents):
        os.rename(rollback_documents, active_documents)
    _safe_remove_tree(data_root, rollback_root)
    _sync_directory(data_root)


def _safe_remove_tree(root: Path, target: Path) -> None:
    target = _validated_direct_child(root, target)
    try:
        metadata = target.lstat()
    except FileNotFoundError:
        return
    _reject_link_or_reparse(
        metadata, message="refusing to remove a link or reparse point"
    )
    if not stat.S_ISDIR(metadata.st_mode):
        raise BackupServiceError("refusing to remove a non-directory path")
    if not (
        target.name.startswith(".backup-work-")
        or target.name.startswith(".restore-work-")
        or _CANDIDATE_PATTERN.fullmatch(target.name)
        or target.name in {_ROLLBACK_DIRECTORY_NAME, ACTIVE_DOCUMENTS_NAME}
    ):
        raise BackupServiceError("refusing to remove an unexpected data path")
    shutil.rmtree(target)


def _validated_direct_child(root: Path, target: Path) -> Path:
    root_absolute = Path(os.path.abspath(root))
    target_absolute = Path(os.path.abspath(target))
    if target_absolute.parent != root_absolute:
        raise BackupServiceError("refusing a path outside the data root")
    return target_absolute


def _path_exists_without_following(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _require_plain_directory(path: Path, *, message: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise BackupServiceError(message) from error
    _reject_link_or_reparse(metadata, message=message)
    if not stat.S_ISDIR(metadata.st_mode):
        raise BackupServiceError(message)


def _reject_link_or_reparse(metadata: os.stat_result, *, message: str) -> None:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(metadata.st_mode) or attributes & reparse_attribute:
        raise BackupServiceError(message)


def _flush_file(path: Path) -> None:
    with path.open("r+b") as handle:
        handle.flush()
        os.fsync(handle.fileno())


def _sync_directory(directory: Path) -> None:
    if os.name != "posix":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _format_timestamp(value: datetime) -> str:
    return _as_utc(value).isoformat().replace("+00:00", "Z")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("backup timestamp must include a timezone")
    return value.astimezone(UTC)
