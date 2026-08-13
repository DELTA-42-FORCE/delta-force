"""Caso de uso: encerra uma sessão de acesso ativa."""

from dataclasses import dataclass

from crm_api.domain.auth.repositories import SessionRepository


@dataclass(frozen=True, slots=True)
class LogoutUseCase:
    """Revoga o token de sessão informado; é idempotente por natureza."""

    sessions: SessionRepository

    async def execute(self, *, session_token: str) -> None:
        await self.sessions.revoke(session_token)
