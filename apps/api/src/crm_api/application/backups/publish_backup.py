"""Application orchestration for encrypted backup publication."""

from __future__ import annotations

from pathlib import Path

from crm_api.infrastructure.backups import container, publisher, snapshot
from crm_api.infrastructure.backups.publisher import (
    BackupPublicationError,
    PublishedBackup,
)
from crm_api.infrastructure.backups.snapshot import BackupSnapshotError
from crm_api.infrastructure.backups.windows_volume import WindowsVolumeInspector


def publish_backup(
    *,
    database_path: Path,
    documents_root: Path,
    temporary_root: Path,
    destination_directory: Path,
    passphrase: str,
    app_version: str,
    created_at: str,
    data_volume_id: str,
    inspector: WindowsVolumeInspector,
) -> PublishedBackup:
    """Snapshot, encrypt directly to an exclusive external partial and publish it."""
    try:
        with snapshot.build_backup_payload(
            database_path=database_path,
            documents_root=documents_root,
            temporary_root=temporary_root,
        ) as payload:

            def write_encrypted_partial(output):
                return container.encrypt_payload_to_stream(
                    payload_path=payload.path,
                    output=output,
                    passphrase=passphrase,
                    app_version=app_version,
                    created_at=created_at,
                    schema_revision=payload.schema_revision,
                )

            return publisher.publish_backup_file(
                payload_bytes=payload.path.stat().st_size,
                destination_directory=destination_directory,
                expected_data_volume_id=data_volume_id,
                inspector=inspector,
                write_encrypted_partial=write_encrypted_partial,
            )
    except BackupPublicationError:
        raise
    except (BackupSnapshotError, container.BackupContainerError, OSError, ValueError):
        raise BackupPublicationError(
            "backup could not be prepared or published safely"
        ) from None
