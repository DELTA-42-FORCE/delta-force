"""Gerações atômicas para ativar banco e documentos como uma unidade."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
from uuid import NAMESPACE_URL, uuid4, uuid5

ACTIVE_POINTER_NAME = "active-generation.json"
ACTIVATION_JOURNAL_NAME = "restore-activation.json"
GENERATIONS_DIRECTORY_NAME = "generations"
DATABASE_NAME = "crm.sqlite3"
DOCUMENTS_NAME = "documents"

_GENERATION_PATTERN = re.compile(r"^generation-[0-9a-f]{32}$")
_PHASES = frozenset({"staged", "pointer_switched"})
_STORAGE_KEY_PATTERN = re.compile(
    r"^[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{32}\.(?:pdf|jpg)$"
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class GenerationLayoutError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ActiveGeneration:
    name: str
    root: Path

    @property
    def database_path(self) -> Path:
        return self.root / DATABASE_NAME

    @property
    def documents_root(self) -> Path:
        return self.root / DOCUMENTS_NAME


@dataclass(frozen=True, slots=True)
class ActivationJournal:
    candidate: str
    previous: str | None
    phase: str
    audit_id: str


def provision_generation_layout(data_root: Path) -> ActiveGeneration:
    """Recupera ativação e cria/migra a primeira geração com segurança."""
    root = data_root.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    generations = root / GENERATIONS_DIRECTORY_NAME
    generations.mkdir(mode=0o700, exist_ok=True)
    _require_plain_directory(generations, "generations root is invalid")
    if (root / ACTIVATION_JOURNAL_NAME).exists():
        activate_pending_generation(root)
    current = read_active_generation(root)
    if current is not None:
        _cleanup_legacy_layout(root)
        return current

    candidate = _new_generation(root)
    try:
        legacy_database = root / DATABASE_NAME
        legacy_documents = root / DOCUMENTS_NAME
        if legacy_database.exists():
            _copy_sqlite_snapshot(legacy_database, candidate.database_path)
        if legacy_documents.exists():
            _copy_documents_tree(legacy_documents, candidate.documents_root)
        elif legacy_database.exists():
            candidate.documents_root.mkdir(mode=0o700)
        if legacy_database.exists():
            _validate_complete_generation(candidate)
        _write_pointer(root, candidate.name)
        _cleanup_legacy_layout(root)
        return candidate
    except BaseException:
        _remove_generation(root, candidate.name)
        raise


def read_active_generation(data_root: Path) -> ActiveGeneration | None:
    root = data_root.resolve()
    pointer = root / ACTIVE_POINTER_NAME
    if not pointer.exists():
        return None
    data = _read_json(pointer, label="active generation pointer")
    if (
        not isinstance(data, dict)
        or set(data) != {"generation", "version"}
        or data.get("version") != 1
        or not isinstance(data.get("generation"), str)
    ):
        raise GenerationLayoutError("active generation pointer is invalid")
    return _generation(root, data["generation"], require_exists=True)


def new_restore_generation(data_root: Path) -> ActiveGeneration:
    root = data_root.resolve()
    generations = root / GENERATIONS_DIRECTORY_NAME
    generations.mkdir(mode=0o700, parents=True, exist_ok=True)
    _require_plain_directory(generations, "generations root is invalid")
    return _new_generation(root)


def stage_activation(data_root: Path, *, candidate: ActiveGeneration) -> None:
    root = data_root.resolve()
    if (root / ACTIVATION_JOURNAL_NAME).exists():
        raise GenerationLayoutError("another restore activation is pending")
    current = read_active_generation(root)
    if current is not None and current.name == candidate.name:
        raise GenerationLayoutError("restore candidate is already active")
    journal = ActivationJournal(
        candidate=candidate.name,
        previous=current.name if current is not None else None,
        phase="staged",
        audit_id=uuid5(NAMESPACE_URL, f"delta-force:{candidate.name}").hex,
    )
    _write_journal(root, journal, exclusive=True)


def activate_pending_generation(data_root: Path) -> bool:
    """Troca um único ponteiro e recupera queda em qualquer fase."""
    root = data_root.resolve()
    journal_path = root / ACTIVATION_JOURNAL_NAME
    if not journal_path.exists():
        return False
    journal = _read_journal(journal_path)
    candidate = _generation(root, journal.candidate, require_exists=True)
    previous = (
        _generation(root, journal.previous, require_exists=True)
        if journal.previous is not None
        else None
    )

    current = read_active_generation(root)
    if current is not None and current.name not in {
        journal.candidate,
        journal.previous,
    }:
        raise GenerationLayoutError("activation journal disagrees with active pointer")
    try:
        if current is None or current.name != candidate.name:
            _validate_complete_generation(candidate)
            _write_pointer(root, candidate.name)
        if journal.phase != "pointer_switched":
            journal = ActivationJournal(
                candidate=journal.candidate,
                previous=journal.previous,
                phase="pointer_switched",
                audit_id=journal.audit_id,
            )
            _write_journal(root, journal, exclusive=False)
        _validate_complete_generation(candidate)
        _record_restore_audit(candidate.database_path, audit_id=journal.audit_id)
    except BaseException:
        if previous is not None:
            _write_pointer(root, previous.name)
        else:
            (root / ACTIVE_POINTER_NAME).unlink(missing_ok=True)
            _sync_directory(root)
        _remove_generation(root, candidate.name)
        journal_path.unlink(missing_ok=True)
        _sync_directory(root)
        raise

    journal_path.unlink(missing_ok=True)
    _sync_directory(root)
    if previous is not None and previous.name != candidate.name:
        _remove_generation(root, previous.name)
    return True


def discard_generation(data_root: Path, generation: ActiveGeneration) -> None:
    _remove_generation(data_root.resolve(), generation.name)


def _new_generation(data_root: Path) -> ActiveGeneration:
    name = f"generation-{uuid4().hex}"
    generation = _generation(data_root, name, require_exists=False)
    generation.root.mkdir(mode=0o700)
    _sync_directory(generation.root.parent)
    return generation


def _generation(
    data_root: Path, name: str | None, *, require_exists: bool
) -> ActiveGeneration:
    if not isinstance(name, str) or not _GENERATION_PATTERN.fullmatch(name):
        raise GenerationLayoutError("generation name is invalid")
    generations = data_root / GENERATIONS_DIRECTORY_NAME
    if require_exists:
        _require_plain_directory(generations, "generations root is invalid")
    path = generations / name
    if path.parent != generations:
        raise GenerationLayoutError("generation escaped its managed root")
    if require_exists:
        _require_plain_directory(path, "generation is unavailable")
    return ActiveGeneration(name=name, root=path)


def _write_pointer(data_root: Path, generation: str) -> None:
    if not _GENERATION_PATTERN.fullmatch(generation):
        raise GenerationLayoutError("generation name is invalid")
    _write_json_atomic(
        data_root / ACTIVE_POINTER_NAME,
        {"generation": generation, "version": 1},
    )


def _write_journal(
    data_root: Path, journal: ActivationJournal, *, exclusive: bool
) -> None:
    path = data_root / ACTIVATION_JOURNAL_NAME
    data = {
        "audit_id": journal.audit_id,
        "candidate": journal.candidate,
        "phase": journal.phase,
        "previous": journal.previous,
        "version": 1,
    }
    if exclusive:
        _write_json_exclusive(path, data)
    else:
        _write_json_atomic(path, data)


def _read_journal(path: Path) -> ActivationJournal:
    data = _read_json(path, label="activation journal")
    if (
        not isinstance(data, dict)
        or set(data) != {"audit_id", "candidate", "phase", "previous", "version"}
        or data.get("version") != 1
        or not isinstance(data.get("candidate"), str)
        or not _GENERATION_PATTERN.fullmatch(data["candidate"])
        or (
            data.get("previous") is not None
            and (
                not isinstance(data["previous"], str)
                or not _GENERATION_PATTERN.fullmatch(data["previous"])
            )
        )
        or data.get("phase") not in _PHASES
        or not isinstance(data.get("audit_id"), str)
        or not re.fullmatch(r"[0-9a-f]{32}", data["audit_id"])
    ):
        raise GenerationLayoutError("activation journal is invalid")
    return ActivationJournal(
        candidate=data["candidate"],
        previous=data["previous"],
        phase=data["phase"],
        audit_id=data["audit_id"],
    )


def _write_json_exclusive(path: Path, value: object) -> None:
    payload = _canonical_json(value)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    _sync_directory(path.parent)


def _write_json_atomic(path: Path, value: object) -> None:
    payload = _canonical_json(value)
    temporary = path.parent / f".{path.name}.{uuid4().hex}.partial"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _read_json(path: Path, *, label: str) -> object:
    try:
        raw = path.read_bytes()
        data = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise GenerationLayoutError(f"{label} is invalid") from None
    if raw != _canonical_json(data):
        raise GenerationLayoutError(f"{label} is not canonical")
    return data


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _copy_sqlite_snapshot(source: Path, destination: Path) -> None:
    _require_plain_regular_file(source, "legacy database is invalid")
    source_uri = f"file:{source.resolve().as_posix()}?mode=ro"
    with (
        closing(sqlite3.connect(source_uri, uri=True)) as source_connection,
        closing(sqlite3.connect(destination)) as destination_connection,
    ):
        source_connection.backup(destination_connection)
        destination_connection.execute("PRAGMA journal_mode=DELETE")
        destination_connection.commit()
    _flush_file(destination)


def _copy_documents_tree(source: Path, destination: Path) -> None:
    _require_plain_directory(source, "legacy document root is invalid")
    destination.mkdir(mode=0o700)
    for current_root, directory_names, filenames in os.walk(source):
        current = Path(current_root)
        _require_plain_directory(current, "legacy document directory is invalid")
        relative = current.relative_to(source)
        target_root = destination / relative
        for directory_name in directory_names:
            child = current / directory_name
            _require_plain_directory(child, "legacy document directory is invalid")
            (target_root / directory_name).mkdir(mode=0o700)
        for filename in filenames:
            child = current / filename
            _require_plain_regular_file(child, "legacy document file is invalid")
            target = target_root / filename
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
            descriptor = os.open(target, flags, 0o600)
            with (
                child.open("rb") as input_handle,
                os.fdopen(descriptor, "wb") as output,
            ):
                shutil.copyfileobj(input_handle, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())


def _validate_complete_generation(generation: ActiveGeneration) -> None:
    _require_plain_regular_file(
        generation.database_path, "generation database is invalid"
    )
    _require_plain_directory(
        generation.documents_root, "generation documents are invalid"
    )
    with closing(sqlite3.connect(generation.database_path)) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        revision = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
        documents = connection.execute(
            "SELECT storage_key, byte_size, checksum_sha256 FROM documents"
        ).fetchall()
    if integrity != ("ok",) or foreign_keys or revision is None:
        raise GenerationLayoutError("generation database failed integrity checks")
    for storage_key, expected_size, expected_digest in documents:
        if (
            not isinstance(storage_key, str)
            or not _STORAGE_KEY_PATTERN.fullmatch(storage_key)
            or type(expected_size) is not int
            or expected_size <= 0
            or not isinstance(expected_digest, str)
            or not _SHA256_PATTERN.fullmatch(expected_digest)
        ):
            raise GenerationLayoutError("generation document metadata is invalid")
        document = generation.documents_root.joinpath(*storage_key.split("/"))
        _require_regular_file_under(
            generation.documents_root,
            document,
            "generation document is invalid",
        )
        actual_size, actual_digest = _hash_file(document)
        if (actual_size, actual_digest) != (expected_size, expected_digest):
            raise GenerationLayoutError("generation document failed verification")


def _record_restore_audit(database_path: Path, *, audit_id: str) -> None:
    from datetime import UTC, datetime

    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO audit_events "
            "(id, occurred_at, actor_kind, actor_user_id, action, "
            "resource_type, resource_id, result, context) "
            "VALUES (?, ?, 'anonymous', NULL, 'backup.restore_applied', "
            "'backup', NULL, 'success', '{}')",
            (audit_id, datetime.now(UTC).isoformat()),
        )
        connection.commit()
    _flush_file(database_path)


def _remove_generation(data_root: Path, name: str) -> None:
    generation = _generation(data_root, name, require_exists=False)
    try:
        metadata = generation.root.lstat()
    except FileNotFoundError:
        return
    _reject_link_or_reparse(metadata, "generation cannot be a link")
    if not stat.S_ISDIR(metadata.st_mode):
        raise GenerationLayoutError("generation is not a directory")
    _remove_plain_tree(generation.root)
    _sync_directory(generation.root.parent)


def _cleanup_legacy_layout(data_root: Path) -> None:
    legacy_database = data_root / DATABASE_NAME
    legacy_documents = data_root / DOCUMENTS_NAME
    if legacy_database.exists():
        _require_plain_regular_file(legacy_database, "legacy database is invalid")
        legacy_database.unlink()
    if legacy_documents.exists():
        _remove_plain_tree(legacy_documents)
    _sync_directory(data_root)


def _remove_plain_tree(path: Path) -> None:
    _require_plain_directory(path, "managed directory is invalid")
    with os.scandir(path) as entries:
        for entry in entries:
            metadata = entry.stat(follow_symlinks=False)
            _reject_link_or_reparse(metadata, "managed path contains a link")
            child = Path(entry.path)
            if stat.S_ISDIR(metadata.st_mode):
                _remove_plain_tree(child)
            elif stat.S_ISREG(metadata.st_mode):
                child.unlink()
            else:
                raise GenerationLayoutError("managed path contains a special file")
    path.rmdir()


def _hash_file(path: Path) -> tuple[int, str]:
    import hashlib

    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            total += len(chunk)
    return total, digest.hexdigest()


def _require_plain_directory(path: Path, message: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise GenerationLayoutError(message) from error
    _reject_link_or_reparse(metadata, message)
    if not stat.S_ISDIR(metadata.st_mode):
        raise GenerationLayoutError(message)


def _require_plain_regular_file(path: Path, message: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise GenerationLayoutError(message) from error
    _reject_link_or_reparse(metadata, message)
    if not stat.S_ISREG(metadata.st_mode):
        raise GenerationLayoutError(message)


def _require_regular_file_under(root: Path, path: Path, message: str) -> None:
    _require_plain_directory(root, message)
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise GenerationLayoutError(message) from None
    current = root
    for part in relative.parts:
        current = current / part
        if current == path:
            _require_plain_regular_file(current, message)
        else:
            _require_plain_directory(current, message)


def _reject_link_or_reparse(metadata: os.stat_result, message: str) -> None:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(metadata.st_mode) or attributes & reparse_attribute:
        raise GenerationLayoutError(message)


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
