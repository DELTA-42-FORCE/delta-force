import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.transactions import Transaction
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.backups.entities import (
    BackupCreationResult,
    RestoreStagingResult,
)
from crm_api.domain.backups.repositories import BackupService, BackupStatusRepository

BACKUP_REMINDER_AFTER = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class BackupStatus:
    last_successful_at: datetime | None
    reminder_due: bool


@dataclass(frozen=True, slots=True)
class CreateBackupUseCase:
    service: BackupService
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        destination_directory: str,
        passphrase: str,
    ) -> BackupCreationResult:
        result = await asyncio.to_thread(
            self.service.create_backup,
            destination_directory=destination_directory,
            passphrase=passphrase,
        )
        try:
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.BACKUP_CREATED,
                resource_type=AuditResourceType.BACKUP,
                resource_id=None,
                result=AuditResult.SUCCESS,
                context={"total_count": str(result.document_count)},
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return result


@dataclass(frozen=True, slots=True)
class StageRestoreUseCase:
    service: BackupService

    async def execute(
        self, *, source_file: str, passphrase: str
    ) -> RestoreStagingResult:
        return await asyncio.to_thread(
            self.service.stage_restore,
            source_file=source_file,
            passphrase=passphrase,
        )


@dataclass(frozen=True, slots=True)
class GetBackupStatusUseCase:
    repository: BackupStatusRepository

    async def execute(self, *, now: datetime | None = None) -> BackupStatus:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        last_successful = await self.repository.last_successful_backup_at()
        return BackupStatus(
            last_successful_at=last_successful,
            reminder_due=(
                last_successful is None
                or current - last_successful.astimezone(UTC) >= BACKUP_REMINDER_AFTER
            ),
        )
