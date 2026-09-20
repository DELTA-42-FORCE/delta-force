from datetime import datetime
from typing import Protocol

from crm_api.domain.backups.entities import (
    BackupCreationResult,
    RestoreStagingResult,
)


class BackupService(Protocol):
    def create_backup(
        self, *, destination_directory: str, passphrase: str
    ) -> BackupCreationResult: ...

    def stage_restore(
        self, *, source_file: str, passphrase: str
    ) -> RestoreStagingResult: ...


class BackupStatusRepository(Protocol):
    async def last_successful_backup_at(self) -> datetime | None: ...
