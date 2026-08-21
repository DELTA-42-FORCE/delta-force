"""Emissão interna de sessões sem decidir transação ou evento de auditoria."""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from crm_api.domain.auth.entities import Session, User
from crm_api.domain.auth.repositories import SessionRepository, SessionTokenHasher


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    """Par usuário/sessão devolvido após autenticação ou primeiro setup."""

    user: User
    session: Session
    session_token: str


@dataclass(frozen=True, slots=True)
class SessionIssuer:
    """Emite o segredo opaco e persiste somente seu hash."""

    sessions: SessionRepository
    token_hasher: SessionTokenHasher
    session_ttl: timedelta

    async def issue(self, *, user: User) -> AuthenticationResult:
        session_token = secrets.token_urlsafe(32)
        session = await self.sessions.create(
            token_hash=self.token_hasher.hash(session_token),
            user_id=user.id,
            expires_at=datetime.now(UTC) + self.session_ttl,
        )
        return AuthenticationResult(
            user=user,
            session=session,
            session_token=session_token,
        )
