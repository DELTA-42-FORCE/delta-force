from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crm_api.domain.audit.entities import AuditAction, AuditResult
from crm_api.infrastructure.audit.models import AuditEventModel
from crm_api.infrastructure.timestamps import as_utc


@dataclass(frozen=True, slots=True)
class SqlAlchemyBackupStatusRepository:
    session: AsyncSession

    async def last_successful_backup_at(self) -> datetime | None:
        statement = (
            select(AuditEventModel.occurred_at)
            .where(
                AuditEventModel.action == AuditAction.BACKUP_CREATED.value,
                AuditEventModel.result == AuditResult.SUCCESS.value,
            )
            .order_by(AuditEventModel.occurred_at.desc(), AuditEventModel.id.desc())
            .limit(1)
        )
        value = await self.session.scalar(statement)
        return as_utc(value) if value is not None else None
