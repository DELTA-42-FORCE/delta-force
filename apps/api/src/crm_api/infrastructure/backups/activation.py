"""Ativação recuperável de uma geração completa restaurada.

Banco e documentos são resolvidos pelo mesmo ponteiro. Um journal durável
permite terminar a troca ou voltar à geração anterior durante o bootstrap.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import sys
import uuid

from alembic.config import Config
from alembic.script import ScriptDirectory

from crm_api.core.config import REPOSITORY_ROOT
from crm_api.infrastructure.documents.storage import provision_document_storage

_LEGACY_GENERATION = "legacy"
_POINTER_FILENAME = "active-generation.json"
_JOURNAL_FILENAME = "restore-activation.json"
_GENERATIONS_DIRECTORY = "generations"
_RESTORE_STAGING_DIRECTORY = "restore-staging"
_RESTORE_WORKSPACE_PREFIX = "backup-restore-"
_STORAGE_KEY = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{32}\.(?:pdf|jpg)$")
_GENERATION_ID = re.compile(r"^[0-9a-f]{32}$")
_MAX_STATE_FILE_BYTES = 4096
_CHUNK_BYTES = 1024 * 1024
_SUMMARY_TABLE_QUERIES = {
    "audit_events": ("audit_events", "SELECT COUNT(*) FROM audit_events"),
    "client_folders": ("clients", "SELECT COUNT(*) FROM client_folders"),
    "contract_installments": (
        "installments",
        "SELECT COUNT(*) FROM contract_installments",
    ),
    "contracts": ("contracts", "SELECT COUNT(*) FROM contracts"),
    "documents": ("documents", "SELECT COUNT(*) FROM documents"),
    "email_dispatches": (
        "email_dispatches",
        "SELECT COUNT(*) FROM email_dispatches",
    ),
    "email_sender_settings": (
        "sender_settings",
        "SELECT COUNT(*) FROM email_sender_settings",
    ),
    "message_templates": (
        "message_templates",
        "SELECT COUNT(*) FROM message_templates",
    ),
    "owner_slot": ("owner_slot", "SELECT COUNT(*) FROM owner_slot"),
    "sessions": ("sessions", "SELECT COUNT(*) FROM sessions"),
    "users": ("users", "SELECT COUNT(*) FROM users"),
}


class RestoreActivationError(Exception):
    """A geração não pôde ser ativada ou recuperada com segurança."""


class RestoreConfirmationRequired(RestoreActivationError):
    """A instalação já contém dados e exige confirmação reforçada."""

    def __init__(self, summary: RestoreImpactSummary) -> None:
        self.summary = summary
        super().__init__("replacing existing CRM data requires explicit confirmation")


@dataclass(frozen=True, slots=True)
class GenerationPaths:
    generation_id: str
    root: Path
    database_path: Path
    documents_root: Path


@dataclass(frozen=True, slots=True)
class RestoreImpactSummary:
    """Contagens sem dados pessoais, para a etapa de revisão da restauração."""

    current_records: dict[str, int]
    candidate_records: dict[str, int]

    @property
    def replaces_existing_data(self) -> bool:
        return any(self.current_records.values())


@dataclass(frozen=True, slots=True)
class RestoreActivationResult:
    generation_id: str
    previous_generation_id: str
    summary: RestoreImpactSummary


def load_active_generation(
    data_directory: Path,
    *,
    initialize_legacy: Callable[[GenerationPaths], None],
) -> GenerationPaths:
    """Recupera journal pendente e resolve o par ativo de banco/documentos.

    Instalações anteriores à #111 são representadas pelo seletor `legacy`,
    que mantém juntos os caminhos já usados pelo aplicativo.
    """
    data_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if _has_reparse_component(data_directory):
        raise RestoreActivationError("CRM data directory is unsafe")
    recover_interrupted_activation(data_directory)
    _cleanup_stale_restore_staging(data_directory)
    generation_id = _read_pointer(data_directory)
    if generation_id is None:
        paths = generation_paths(data_directory, _LEGACY_GENERATION)
        initialize_legacy(paths)
        _write_pointer(data_directory, _LEGACY_GENERATION)
        return paths
    paths = generation_paths(data_directory, generation_id)
    if not _generation_paths_are_safe(paths):
        raise RestoreActivationError("active CRM generation is incomplete")
    return paths


def generation_paths(data_directory: Path, generation_id: str) -> GenerationPaths:
    """Retorna caminhos de um seletor validado, sem aceitar traversal."""
    if generation_id == _LEGACY_GENERATION:
        root = data_directory
    elif _GENERATION_ID.fullmatch(generation_id):
        root = data_directory / _GENERATIONS_DIRECTORY / generation_id
    else:
        raise RestoreActivationError("generation selector is invalid")
    return GenerationPaths(
        generation_id=generation_id,
        root=root,
        database_path=root / "crm.sqlite3",
        documents_root=root / "documents",
    )


def activate_restore_candidate(
    *,
    data_directory: Path,
    candidate_root: Path,
    confirm_replacement: bool,
    close_active_connections: Callable[[], None],
) -> RestoreActivationResult:
    """Publica candidata validada e troca o par ativo por um único ponteiro.

    `close_active_connections` deve descartar sessões/engine antes da troca.
    A autenticação do proprietário e a confirmação forte pertencem ao chamador;
    esta camada exige a confirmação quando já existem registros no CRM.
    """
    recover_interrupted_activation(data_directory)
    previous_id = _read_pointer(data_directory)
    if previous_id is None:
        raise RestoreActivationError("active CRM generation has not been initialized")
    previous = generation_paths(data_directory, previous_id)
    if not _generation_paths_are_safe(previous):
        raise RestoreActivationError("active CRM generation is incomplete")
    candidate = _validate_candidate_root(candidate_root)
    current_records = _record_counts(previous.database_path)
    candidate_records = _record_counts(candidate.database_path)
    summary = RestoreImpactSummary(current_records, candidate_records)
    if summary.replaces_existing_data and not confirm_replacement:
        raise RestoreConfirmationRequired(summary)

    generations_root = data_directory / _GENERATIONS_DIRECTORY
    generations_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if _has_reparse_component(generations_root):
        raise RestoreActivationError("generation storage directory is unsafe")
    generation_id = uuid.uuid4().hex
    destination = generation_paths(data_directory, generation_id)
    _require_same_volume(candidate.root, generations_root)
    journal = {
        "candidate": generation_id,
        "format_version": 1,
        "phase": "prepared",
        "previous": previous_id,
    }
    try:
        _write_journal(data_directory, journal)
        candidate.database_path.replace(candidate.root / "crm.sqlite3")
        _sync_tree(candidate.root)
        _move_directory_durably(candidate.root, destination.root)
        _sync_tree(destination.root)
        provision_document_storage(destination.documents_root)
        _validate_generation(destination)
        journal["phase"] = "candidate_ready"
        _write_journal(data_directory, journal)
        close_active_connections()
        _write_pointer(data_directory, generation_id)
        journal["phase"] = "switched"
        _write_journal(data_directory, journal)
        _validate_generation(destination)
        journal["phase"] = "validated"
        _write_journal(data_directory, journal)
        _remove_previous_generation(data_directory, previous_id)
        _remove_journal(data_directory)
    except Exception as error:
        raise RestoreActivationError(
            "restore activation was interrupted and will be recovered at startup"
        ) from error
    return RestoreActivationResult(generation_id, previous_id, summary)


def recover_interrupted_activation(data_directory: Path) -> None:
    """Finaliza a candidata íntegra ou restaura o seletor anterior."""
    if _has_reparse_component(data_directory):
        raise RestoreActivationError("CRM data directory is unsafe")
    journal = _read_journal(data_directory)
    if journal is None:
        return
    previous_id = journal["previous"]
    candidate_id = journal["candidate"]
    current_id = _read_pointer(data_directory)
    if current_id not in {previous_id, candidate_id}:
        raise RestoreActivationError("restore journal does not match active generation")

    candidate = generation_paths(data_directory, candidate_id)
    if journal["phase"] != "rolling_back" and _generation_is_valid(candidate):
        _write_pointer(data_directory, candidate_id)
        journal["phase"] = "validated"
        _write_journal(data_directory, journal)
        _remove_previous_generation(data_directory, previous_id)
        _remove_journal(data_directory)
        return

    previous = generation_paths(data_directory, previous_id)
    if not _generation_is_valid(previous):
        raise RestoreActivationError("neither restore generation is recoverable")
    journal["phase"] = "rolling_back"
    _write_journal(data_directory, journal)
    _write_pointer(data_directory, previous_id)
    _remove_known_generation(data_directory, candidate_id)
    _remove_journal(data_directory)


def _validate_candidate_root(candidate_root: Path) -> GenerationPaths:
    if _has_reparse_component(candidate_root) or not candidate_root.is_dir():
        raise RestoreActivationError("restore candidate directory is unsafe")
    candidate = GenerationPaths(
        generation_id="candidate",
        root=candidate_root,
        database_path=candidate_root / "db.sqlite3",
        documents_root=candidate_root / "documents",
    )
    _validate_generation(candidate, database_name="db.sqlite3")
    return candidate


def _validate_generation(
    paths: GenerationPaths, *, database_name: str = "crm.sqlite3"
) -> None:
    database_path = paths.root / database_name
    if (
        _has_reparse_component(paths.root)
        or _has_reparse_component(database_path)
        or _has_reparse_component(paths.documents_root)
        or not database_path.is_file()
        or not paths.documents_root.is_dir()
    ):
        raise RestoreActivationError("CRM generation paths are unsafe")
    try:
        with sqlite3.connect(_readonly_uri(database_path), uri=True) as database:
            integrity = database.execute("PRAGMA integrity_check").fetchone()
            foreign_key_errors = database.execute("PRAGMA foreign_key_check").fetchall()
            revisions = database.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchall()
            documents = database.execute(
                "SELECT storage_key, byte_size, checksum_sha256 "
                "FROM documents ORDER BY storage_key"
            ).fetchall()
    except sqlite3.Error:
        raise RestoreActivationError("CRM generation database is invalid") from None
    if integrity != ("ok",) or foreign_key_errors or len(revisions) != 1:
        raise RestoreActivationError("CRM generation database is invalid")
    revision = revisions[0][0]
    if not isinstance(revision, str) or not _known_revision(revision):
        raise RestoreActivationError("CRM generation schema is unsupported")
    _verify_document_files(paths.documents_root, documents)


def _generation_is_valid(paths: GenerationPaths) -> bool:
    try:
        _validate_generation(paths)
    except (OSError, RestoreActivationError, ValueError):
        return False
    return True


def _record_counts(database_path: Path) -> dict[str, int]:
    try:
        with sqlite3.connect(_readonly_uri(database_path), uri=True) as database:
            table_names = {
                row[0]
                for row in database.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
                )
            }
            counts: dict[str, int] = {}
            for table_name, (label, query) in _SUMMARY_TABLE_QUERIES.items():
                if table_name not in table_names:
                    continue
                count = database.execute(query).fetchone()[0]
                if count:
                    counts[label] = count
            unclassified_tables = table_names - _SUMMARY_TABLE_QUERIES.keys()
            if unclassified_tables:
                counts["other_tables"] = len(unclassified_tables)
            return counts
    except sqlite3.Error:
        raise RestoreActivationError("CRM data summary could not be created") from None


def _verify_document_files(
    documents_root: Path, rows: list[tuple[object, ...]]
) -> None:
    for row in rows:
        if len(row) != 3:
            raise RestoreActivationError("CRM document metadata is invalid")
        storage_key, byte_size, expected_digest = row
        if (
            not isinstance(storage_key, str)
            or not _STORAGE_KEY.fullmatch(storage_key)
            or type(byte_size) is not int
            or byte_size < 0
            or not isinstance(expected_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_digest)
        ):
            raise RestoreActivationError("CRM document metadata is invalid")
        path = documents_root.joinpath(*storage_key.split("/"))
        if _has_reparse_component(path) or not path.is_file():
            raise RestoreActivationError("CRM generation document is missing")
        digest = hashlib.sha256()
        byte_count = 0
        with path.open("rb") as content:
            while chunk := content.read(_CHUNK_BYTES):
                digest.update(chunk)
                byte_count += len(chunk)
        if byte_count != byte_size or digest.hexdigest() != expected_digest:
            raise RestoreActivationError("CRM generation document is invalid")


def _known_revision(revision: str) -> bool:
    if getattr(sys, "frozen", False):
        api_root = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        api_root = REPOSITORY_ROOT / "apps" / "api"
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    try:
        return ScriptDirectory.from_config(config).get_revision(revision) is not None
    except Exception:
        return False


def _read_pointer(data_directory: Path) -> str | None:
    state_path = data_directory / _POINTER_FILENAME
    if not _path_exists_including_dangling_link(state_path):
        return None
    value = _read_state_file(state_path)
    if set(value) != {"format_version", "generation"}:
        raise RestoreActivationError("active generation pointer is invalid")
    generation_id = value["generation"]
    if (
        type(value["format_version"]) is not int
        or value["format_version"] != 1
        or not isinstance(generation_id, str)
        or not _valid_generation_id(generation_id)
    ):
        raise RestoreActivationError("active generation pointer is invalid")
    return generation_id


def _write_pointer(data_directory: Path, generation_id: str) -> None:
    if not _valid_generation_id(generation_id):
        raise RestoreActivationError("generation selector is invalid")
    _atomic_write_json(
        data_directory / _POINTER_FILENAME,
        {"format_version": 1, "generation": generation_id},
    )


def _read_journal(data_directory: Path) -> dict[str, str | int] | None:
    journal_path = data_directory / _JOURNAL_FILENAME
    if not _path_exists_including_dangling_link(journal_path):
        return None
    value = _read_state_file(journal_path)
    if set(value) != {"format_version", "previous", "candidate", "phase"}:
        raise RestoreActivationError("restore journal is invalid")
    if (
        type(value["format_version"]) is not int
        or value["format_version"] != 1
        or not isinstance(value["previous"], str)
        or not _valid_generation_id(value["previous"])
        or not isinstance(value["candidate"], str)
        or not _GENERATION_ID.fullmatch(value["candidate"])
        or value["previous"] == value["candidate"]
        or not isinstance(value["phase"], str)
        or value["phase"]
        not in {
            "prepared",
            "candidate_ready",
            "switched",
            "validated",
            "rolling_back",
        }
    ):
        raise RestoreActivationError("restore journal is invalid")
    return value  # type: ignore[return-value]


def _write_journal(data_directory: Path, journal: dict[str, str | int]) -> None:
    _atomic_write_json(data_directory / _JOURNAL_FILENAME, journal)


def _read_state_file(path: Path) -> dict[str, object]:
    try:
        metadata = path.lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size > _MAX_STATE_FILE_BYTES
        ):
            raise RestoreActivationError("restore state file is unsafe")
        content = path.read_bytes()
        value = json.loads(content)
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    except (OSError, ValueError, TypeError):
        raise RestoreActivationError("restore state file is invalid") from None
    if not isinstance(value, dict) or content != canonical:
        raise RestoreActivationError("restore state file is invalid")
    return value


def _atomic_write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    content = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(
        temporary_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        _replace_durably(temporary_path, path)
        _sync_directory(path.parent)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _replace_durably(source: Path, destination: Path) -> None:
    if os.name != "nt":
        os.replace(source, destination)
        return
    move_file_ex = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
    move_file_ex.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
    move_file_ex.restype = ctypes.c_int
    flags = 0x1 | 0x8  # MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH
    if not move_file_ex(str(source), str(destination), flags):
        raise ctypes.WinError(ctypes.get_last_error())


def _move_directory_durably(source: Path, destination: Path) -> None:
    if os.name != "nt":
        os.replace(source, destination)
        _sync_directory(destination.parent)
        return
    move_file_ex = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
    move_file_ex.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
    move_file_ex.restype = ctypes.c_int
    if not move_file_ex(str(source), str(destination), 0x8):
        raise ctypes.WinError(ctypes.get_last_error())


def _sync_tree(root: Path) -> None:
    for current_root, directory_names, file_names in os.walk(root):
        current = Path(current_root)
        for name in file_names:
            path = current / name
            if _has_reparse_component(path) or not path.is_file():
                raise RestoreActivationError("restore candidate tree is unsafe")
            mode = "rb+" if os.name == "nt" else "rb"
            with path.open(mode) as content:
                os.fsync(content.fileno())
        if os.name != "nt":
            _sync_directory(current)
        for name in directory_names:
            if _has_reparse_component(current / name):
                raise RestoreActivationError("restore candidate tree is unsafe")


def _sync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _remove_journal(data_directory: Path) -> None:
    (data_directory / _JOURNAL_FILENAME).unlink(missing_ok=True)
    _sync_directory(data_directory)


def _cleanup_stale_restore_staging(data_directory: Path) -> None:
    staging_root = data_directory / _RESTORE_STAGING_DIRECTORY
    if not _path_exists_including_dangling_link(staging_root):
        return
    if _has_reparse_component(staging_root) or not staging_root.is_dir():
        raise RestoreActivationError("restore staging directory is unsafe")
    try:
        workspaces = tuple(staging_root.iterdir())
    except OSError:
        raise RestoreActivationError(
            "restore staging directory is unavailable"
        ) from None
    for workspace in workspaces:
        if not workspace.name.startswith(_RESTORE_WORKSPACE_PREFIX):
            continue
        if _has_reparse_component(workspace):
            raise RestoreActivationError("restore staging workspace is unsafe")
        if workspace.is_dir():
            shutil.rmtree(workspace)
    _sync_directory(staging_root)


def _remove_known_generation(data_directory: Path, generation_id: str) -> None:
    if not _GENERATION_ID.fullmatch(generation_id):
        return
    path = generation_paths(data_directory, generation_id).root
    if path.exists() and not _has_reparse_component(path):
        shutil.rmtree(path)
        _sync_directory(path.parent)


def _remove_previous_generation(data_directory: Path, generation_id: str) -> None:
    """Libera a geração anterior somente depois da candidata estar validada."""
    if generation_id != _LEGACY_GENERATION:
        _remove_known_generation(data_directory, generation_id)
        return
    paths = generation_paths(data_directory, generation_id)
    if _has_reparse_component(paths.root) or _has_reparse_component(
        paths.documents_root
    ):
        return
    try:
        for name in ("crm.sqlite3", "crm.sqlite3-wal", "crm.sqlite3-shm"):
            file_path = paths.root / name
            if _path_exists_including_dangling_link(file_path):
                if _has_reparse_component(file_path):
                    return
                file_path.unlink()
        if paths.documents_root.is_dir():
            shutil.rmtree(paths.documents_root)
        _sync_directory(data_directory)
    except OSError:
        # A candidata já está íntegra e ativa; sobras não participam da seleção.
        return


def _valid_generation_id(value: str) -> bool:
    return value == _LEGACY_GENERATION or bool(_GENERATION_ID.fullmatch(value))


def _generation_paths_are_safe(paths: GenerationPaths) -> bool:
    return (
        not _has_reparse_component(paths.root)
        and not _has_reparse_component(paths.database_path)
        and not _has_reparse_component(paths.documents_root)
        and paths.database_path.is_file()
        and paths.documents_root.is_dir()
    )


def _path_exists_including_dangling_link(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _require_same_volume(source: Path, destination_parent: Path) -> None:
    source_device = source.stat().st_dev
    destination_device = destination_parent.stat().st_dev
    if source_device != destination_device:
        raise RestoreActivationError("restore staging must be on the data volume")


def _has_reparse_component(path: Path) -> bool:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            return False
        except OSError:
            return True
        if stat.S_ISLNK(metadata.st_mode) or getattr(
            metadata, "st_file_attributes", 0
        ) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            return True
    return False


def _readonly_uri(path: Path) -> str:
    return f"{path.resolve().as_uri()}?mode=ro"
