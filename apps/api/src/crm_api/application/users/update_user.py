"""Caso de uso: administrador edita nome ou papel de uma conta interna."""

from dataclasses import dataclass
from uuid import UUID

from crm_api.domain.auth.entities import User
from crm_api.domain.auth.repositories import UserRepository
from crm_api.domain.users.errors import UserNotFoundError


@dataclass(frozen=True, slots=True)
class UpdateUserUseCase:
    """Atualiza campos editáveis; ``None`` mantém o valor atual."""

    users: UserRepository

    async def execute(
        self, *, user_id: UUID, full_name: str | None, is_admin: bool | None
    ) -> User:
        user = await self.users.update(
            user_id=user_id, full_name=full_name, is_admin=is_admin
        )
        if user is None:
            raise UserNotFoundError

        return user
