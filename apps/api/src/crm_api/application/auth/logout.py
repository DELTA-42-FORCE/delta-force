"""Caso de uso: encerra uma sessão de acesso ativa."""

from dataclasses import dataclass
from uuid import UUID

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.transactions import Transaction
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.auth.repositories import SessionRepository, SessionTokenHasher


@dataclass(frozen=True, slots=True)
class LogoutUseCase:
    """Revoga o token de sessão informado; é idempotente por natureza."""

    sessions: SessionRepository
    token_hasher: SessionTokenHasher
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(self, *, session_token: str, actor_user_id: UUID) -> None:
        try:
            await self.sessions.revoke_by_token_hash(
                self.token_hasher.hash(session_token)
            )
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.LOGOUT,
                resource_type=AuditResourceType.SESSION,
                resource_id=None,
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
