from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.backups.manage_backups import (
    CreateBackupUseCase,
    GetBackupStatusUseCase,
    StageRestoreUseCase,
)
from crm_api.core.config import get_settings
from crm_api.infrastructure.audit.repositories import SqlAlchemyAuditEventRepository
from crm_api.infrastructure.audit.transactions import SqlAlchemyTransaction
from crm_api.infrastructure.backups.media import BackupMediaPolicy
from crm_api.infrastructure.backups.repositories import (
    SqlAlchemyBackupStatusRepository,
)
from crm_api.infrastructure.backups.service import EncryptedBackupService
from crm_api.presentation.dependencies import DatabaseSession


def _service() -> EncryptedBackupService:
    settings = get_settings()
    database_path = settings.database_path
    data_root = settings.data_root_path
    return EncryptedBackupService(
        data_root=data_root,
        database_path=database_path,
        documents_root=settings.documents_root_path,
        media_policy=BackupMediaPolicy(
            data_root=data_root,
            allow_local_destination=settings.allow_local_backup_destination,
        ),
    )


def get_create_backup_use_case(session: DatabaseSession) -> CreateBackupUseCase:
    return CreateBackupUseCase(
        service=_service(),
        audit=RecordAuditEventUseCase(SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )


def get_backup_status_use_case(session: DatabaseSession) -> GetBackupStatusUseCase:
    return GetBackupStatusUseCase(repository=SqlAlchemyBackupStatusRepository(session))


def get_stage_restore_use_case() -> StageRestoreUseCase:
    return StageRestoreUseCase(service=_service())
