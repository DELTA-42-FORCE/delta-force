"""Caso de uso: encerra uma sessão de acesso ativa."""

from dataclasses import dataclass

from crm_api.domain.auth.repositories import SessionRepository, SessionTokenHasher


@dataclass(frozen=True, slots=True)
class LogoutUseCase:
    """Revoga o token de sessão informado; é idempotente por natureza."""

    sessions: SessionRepository
    token_hasher: SessionTokenHasher

    async def execute(self, *, session_token: str) -> None:
        await self.sessions.revoke_by_token_hash(self.token_hasher.hash(session_token))
