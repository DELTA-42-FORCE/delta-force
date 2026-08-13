"""Caso de uso: administrador consulta as contas internas cadastradas."""

from dataclasses import dataclass

from crm_api.domain.auth.entities import User
from crm_api.domain.auth.repositories import UserRepository


@dataclass(frozen=True, slots=True)
class ListUsersUseCase:
    """Lista todas as contas internas, ativas ou não."""

    users: UserRepository

    async def execute(self) -> list[User]:
        return await self.users.list_all()
