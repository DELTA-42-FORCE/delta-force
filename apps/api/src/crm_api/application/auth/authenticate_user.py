"""Caso de uso de login: emite uma sessão para uma conta interna válida."""

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
from crm_api.domain.auth.errors import InactiveUserError, InvalidCredentialsError
from crm_api.domain.auth.repositories import (
    PasswordHasher,
    UserRepository,
)


@dataclass(frozen=True, slots=True)
class AuthenticateUserUseCase:
    """Valida credenciais e cria uma sessão de acesso."""

    users: UserRepository
    password_hasher: PasswordHasher
    session_issuer: SessionIssuer
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(self, *, email: str, password: str) -> AuthenticationResult:
        user = await self.users.find_by_email(email)
        password_hash = (
            user.password_hash if user is not None else self.password_hasher.dummy_hash
        )
        credentials_match = self.password_hasher.verify(
            password=password, password_hash=password_hash
        )

        if user is None or not credentials_match:
            await self._record_denied_login()
            raise InvalidCredentialsError

        if not user.is_active:
            await self._record_denied_login()
            raise InactiveUserError

        try:
            result = await self.session_issuer.issue(user=user)
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=user.id,
                action=AuditAction.LOGIN,
                resource_type=AuditResourceType.OWNER_ACCOUNT,
                resource_id=str(user.id),
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return result

    async def _record_denied_login(self) -> None:
        try:
            await self.audit.execute(
                actor_kind=AuditActorKind.ANONYMOUS,
                actor_user_id=None,
                action=AuditAction.LOGIN,
                resource_type=AuditResourceType.OWNER_ACCOUNT,
                resource_id=None,
                result=AuditResult.DENIED,
                context={"reason_code": "invalid_credentials"},
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise


__all__ = ["AuthenticateUserUseCase", "AuthenticationResult"]
