"""Caso de uso: resolve o usuário autenticado a partir de um token de sessão."""

from dataclasses import dataclass
from datetime import UTC, datetime

from crm_api.domain.auth.entities import User
from crm_api.domain.auth.errors import InactiveUserError, InvalidSessionError
from crm_api.domain.auth.repositories import (
    SessionRepository,
    SessionTokenHasher,
    UserRepository,
)


@dataclass(frozen=True, slots=True)
class GetCurrentUserUseCase:
    """Garante que só sessões ativas e não expiradas acessem recursos protegidos."""

    sessions: SessionRepository
    users: UserRepository
    token_hasher: SessionTokenHasher

    async def execute(self, *, session_token: str) -> User:
        session = await self.sessions.find_by_token_hash(
            self.token_hasher.hash(session_token)
        )
        if session is None or not session.is_valid(now=datetime.now(UTC)):
            raise InvalidSessionError

        user = await self.users.find_by_id(session.user_id)
        if user is None or not user.is_active:
            raise InactiveUserError

        return user
