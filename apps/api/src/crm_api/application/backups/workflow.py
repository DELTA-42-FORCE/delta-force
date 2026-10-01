"""Fluxo desktop de backup: revisão sem plaintext retido e ativação exclusiva."""

from __future__ import annotations

import asyncio
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
from pathlib import Path
import shutil
import sqlite3
import time
from uuid import UUID, uuid4

from crm_api.application.backups.publish_backup import publish_backup
from crm_api.infrastructure.backups.activation import (
    RestoreActivationError,
    _has_reparse_component,
    _atomic_write_json,
    _read_state_file,
    activate_restore_candidate,
    inspect_restore_impact,
    resolve_active_generation,
)
from crm_api.infrastructure.backups.container import (
    maximum_encrypted_size,
    read_backup_header,
)
from crm_api.infrastructure.backups.restore import stage_backup_restore
from crm_api.infrastructure.backups.windows_volume import WindowsVolumeInspector

_MARGIN = 64 * 1024 * 1024
_PREVIEW_TTL = 600


class StaleRestorePreviewError(Exception):
    """A prévia expirou ou seu arquivo/estado foi alterado."""


@dataclass(frozen=True)
class _Preview:
    owner_id: UUID
    source: Path
    digest: str
    generation_id: str
    expires_at: float


class DesktopBackupWorkflow:
    """Uma instância por sidecar; caminhos e tokens nunca entram na auditoria.

    A trava ASGI deve abranger respostas, streams e finalização de dependências.
    Isso impede consultas/escritas sobre a geração que está sendo trocada.
    Prévias guardam apenas descritores em memória; o staging é sempre descartado.
    """

    def __init__(self, data_directory: Path) -> None:
        self.data_directory = data_directory
        self.lock = asyncio.Lock()
        self.recovery_required = False
        self._previews: dict[str, _Preview] = {}

    def invalidate_previews(self) -> None:
        self._previews.clear()

    @property
    def _preferences_path(self) -> Path:
        return self.data_directory / "backup-reminder.json"

    def status(self) -> dict[str, object]:
        preferences = {"interval_days": None, "last_backup_at": None}
        if self._preferences_path.exists():
            preferences = _read_state_file(self._preferences_path)
        interval = preferences.get("interval_days")
        last = preferences.get("last_backup_at")
        if interval is not None and (
            type(interval) is not int or not 1 <= interval <= 365
        ):
            raise ValueError("invalid backup reminder interval")
        if last is not None and not isinstance(last, str):
            raise ValueError("invalid backup reminder timestamp")
        last_time = datetime.fromisoformat(last) if last is not None else None
        if last_time is not None and last_time.tzinfo is None:
            raise ValueError("invalid backup reminder timestamp")
        due = interval is not None and (
            last_time is None
            or datetime.now(UTC) >= last_time + timedelta(days=interval)
        )
        return {
            "interval_days": interval,
            "last_backup_at": last,
            "reminder_due": due,
            "recovery_required": self.recovery_required,
        }

    def configure_reminder(self, interval_days: int | None) -> dict[str, object]:
        if interval_days is not None and (
            type(interval_days) is not int or not 1 <= interval_days <= 365
        ):
            raise ValueError("invalid backup reminder interval")
        current = self.status()
        _atomic_write_json(
            self._preferences_path,
            {
                "interval_days": interval_days,
                "last_backup_at": current["last_backup_at"],
            },
        )
        return self.status()

    def estimate(self, destination: str) -> dict[str, int]:
        active = resolve_active_generation(self.data_directory)
        inspector = WindowsVolumeInspector()
        data_volume = inspector.identify_volume(self.data_directory)
        # O WAL é incluído conservadoramente; o snapshot concreto é medido e
        # revalidado pelo publicador antes da escrita no HD externo.
        database_bytes = active.database_path.stat().st_size
        wal = active.database_path.with_name(active.database_path.name + "-wal")
        if wal.exists():
            database_bytes += wal.stat().st_size
        with closing(
            sqlite3.connect(active.database_path.as_uri() + "?mode=ro", uri=True)
        ) as db:
            document_bytes, document_count = db.execute(
                "SELECT COALESCE(SUM(byte_size), 0), COUNT(*) FROM documents"
            ).fetchone()
        payload_bytes = (
            database_bytes + document_bytes + document_count * 4096 + 16 * 1024 * 1024
        )
        with inspector.open_directory(
            self._absolute_path(destination),
            expected_data_volume_id=data_volume.volume_id,
        ) as volume:
            external_free = shutil.disk_usage(volume.identity.canonical_directory).free
        return {
            "required_bytes": maximum_encrypted_size(payload_bytes) + _MARGIN,
            "available_bytes": external_free,
            "local_required_bytes": payload_bytes * 2 + _MARGIN,
            "local_available_bytes": shutil.disk_usage(self.data_directory).free,
        }

    def create_backup(self, destination: str, passphrase: str) -> dict[str, bool]:
        current = self.status()
        estimate = self.estimate(destination)
        if (
            estimate["required_bytes"] > estimate["available_bytes"]
            or estimate["local_required_bytes"] > estimate["local_available_bytes"]
        ):
            raise OSError("insufficient backup space")
        active = resolve_active_generation(self.data_directory)
        inspector = WindowsVolumeInspector()
        created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        publish_backup(
            database_path=active.database_path,
            documents_root=active.documents_root,
            temporary_root=self.data_directory / "backup-staging",
            destination_directory=self._absolute_path(destination),
            passphrase=passphrase,
            app_version="0.1.0",
            created_at=created_at,
            data_volume_id=inspector.identify_volume(self.data_directory).volume_id,
            inspector=inspector,
        )
        try:
            _atomic_write_json(
                self._preferences_path,
                {
                    "interval_days": current["interval_days"],
                    "last_backup_at": created_at,
                },
            )
        except OSError:
            # A publicação já foi verificada. Falhar o lembrete não desfaz a cópia.
            return {"completed": True, "reminder_updated": False}
        return {"completed": True, "reminder_updated": True}

    def preview_restore(
        self, source: str, passphrase: str, owner_id: UUID
    ) -> dict[str, object]:
        self.invalidate_previews()
        source_path = self._absolute_path(source)
        if _has_reparse_component(source_path) or not source_path.is_file():
            raise ValueError("backup source is not a regular local file")
        read_backup_header(source_path)
        original_digest = self._digest(source_path)
        with stage_backup_restore(
            source_path=source_path,
            passphrase=passphrase,
            temporary_root=self.data_directory / "restore-staging",
        ) as candidate:
            # Somente o banco autenticado no staging é migrado; o ativo não muda.
            self._prepare_candidate(candidate.database_path, applied=False)
            summary = inspect_restore_impact(self.data_directory, candidate.root)
            digest = self._digest(source_path)
            if digest != original_digest:
                raise StaleRestorePreviewError
            token = uuid4().hex
            self._previews[token] = _Preview(
                owner_id,
                source_path,
                digest,
                resolve_active_generation(self.data_directory).generation_id,
                time.monotonic() + _PREVIEW_TTL,
            )
            return {
                "preview_token": token,
                "current_records": summary.current_records,
                "candidate_records": summary.candidate_records,
                "replacement_required": summary.replaces_existing_data,
                "expires_in_seconds": _PREVIEW_TTL,
            }

    def apply_restore(self, token: str, passphrase: str, owner_id: UUID) -> None:
        preview = self._previews.pop(token, None)
        if (
            preview is None
            or preview.owner_id != owner_id
            or time.monotonic() >= preview.expires_at
            or resolve_active_generation(self.data_directory).generation_id
            != preview.generation_id
        ):
            raise StaleRestorePreviewError
        if self._digest(preview.source) != preview.digest:
            raise StaleRestorePreviewError
        try:
            self._apply_staged_restore(preview, passphrase)
        except RestoreActivationError:
            self.recovery_required = True
            raise
        self.invalidate_previews()

    def _apply_staged_restore(self, preview: _Preview, passphrase: str) -> None:
        activation_started = False
        try:
            with stage_backup_restore(
                source_path=preview.source,
                passphrase=passphrase,
                temporary_root=self.data_directory / "restore-staging",
            ) as candidate:
                if self._digest(preview.source) != preview.digest:
                    raise StaleRestorePreviewError
                self._prepare_candidate(candidate.database_path, applied=True)
                activation_started = True
                activate_restore_candidate(
                    data_directory=self.data_directory,
                    candidate_root=candidate.root,
                    confirm_replacement=True,
                    close_active_connections=lambda: None,
                )
                from crm_api.desktop_server import _use_active_generation

                _use_active_generation(resolve_active_generation(self.data_directory))
        except Exception as error:
            if activation_started:
                raise RestoreActivationError(
                    "restore requires startup recovery"
                ) from error
            raise

    @staticmethod
    def _absolute_path(value: str) -> Path:
        path = Path(value)
        if not path.is_absolute() or value.startswith("\\\\"):
            raise ValueError("selection must be an absolute native path")
        return path

    @staticmethod
    def _digest(path: Path) -> str:
        if _has_reparse_component(path) or not path.is_file():
            raise ValueError("backup source is not a regular local file")
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _prepare_candidate(path: Path, *, applied: bool) -> None:
        from crm_api.desktop_server import _upgrade_candidate

        _upgrade_candidate(path)
        if not applied:
            return
        with closing(sqlite3.connect(path)) as database:
            database.execute("DELETE FROM sessions")
            # O ator da autorização está no log anterior. O evento no backup
            # restaurado representa a ativação pelo sistema, sem fingir que uma
            # conta eventualmente diferente autorizou a operação.
            database.execute(
                "INSERT INTO audit_events (id, occurred_at, actor_kind, actor_user_id, "
                "action, resource_type, resource_id, result, context) "
                "VALUES (?, ?, 'anonymous', NULL, 'backup.restore_applied', "
                "'backup', NULL, 'success', '{}')",
                (uuid4().hex, datetime.now(UTC).replace(tzinfo=None).isoformat(" ")),
            )
            database.commit()
            database.execute("PRAGMA wal_checkpoint(TRUNCATE)")
