"""Consulta auditada dos dados da conta proprietária autenticada."""

from dataclasses import dataclass

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.transactions import Transaction
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.auth.entities import User


@dataclass(frozen=True, slots=True)
class ViewOwnerProfileUseCase:
    """Registra a consulta e devolve o perfil já autenticado."""

    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(self, *, user: User) -> User:
        try:
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=user.id,
                action=AuditAction.OWNER_PROFILE_VIEW,
                resource_type=AuditResourceType.OWNER_ACCOUNT,
                resource_id=str(user.id),
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return user
