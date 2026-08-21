"""Primeira configuração da conta única do proprietário."""

from dataclasses import dataclass

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.auth.session_issuer import (
    AuthenticationResult,
    SessionIssuer,
)
from crm_api.application.transactions import Transaction
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.auth.errors import SetupAlreadyCompletedError
from crm_api.domain.auth.repositories import PasswordHasher, UserRepository


@dataclass(frozen=True, slots=True)
class SetupOwnerUseCase:
    """Cria a única conta inicial e já inicia sua primeira sessão."""

    users: UserRepository
    password_hasher: PasswordHasher
    session_issuer: SessionIssuer
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self, *, email: str, full_name: str, password: str
    ) -> AuthenticationResult:
        try:
            owner = await self.users.create_owner_if_none(
                email=email,
                full_name=full_name,
                password_hash=self.password_hasher.hash(password),
            )
        except Exception:
            await self.transaction.rollback()
            raise
        if owner is None:
            await self._record_denied_setup()
            raise SetupAlreadyCompletedError

        try:
            result = await self.session_issuer.issue(user=owner)
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=owner.id,
                action=AuditAction.OWNER_SETUP,
                resource_type=AuditResourceType.OWNER_ACCOUNT,
                resource_id=str(owner.id),
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return result

    async def _record_denied_setup(self) -> None:
        try:
            await self.audit.execute(
                actor_kind=AuditActorKind.ANONYMOUS,
                actor_user_id=None,
                action=AuditAction.OWNER_SETUP,
                resource_type=AuditResourceType.OWNER_ACCOUNT,
                resource_id=None,
                result=AuditResult.DENIED,
                context={"reason_code": "setup_already_completed"},
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise


@dataclass(frozen=True, slots=True)
class GetSetupStatusUseCase:
    """Informa à interface se a primeira configuração ainda é necessária."""

    users: UserRepository

    async def execute(self) -> bool:
        return not await self.users.has_any()
