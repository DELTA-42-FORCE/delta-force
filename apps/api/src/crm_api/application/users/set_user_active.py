"""Caso de uso: administrador ativa ou desativa uma conta interna."""

from dataclasses import dataclass
from uuid import UUID

from crm_api.domain.auth.entities import User
from crm_api.domain.auth.repositories import UserRepository
from crm_api.domain.users.errors import CannotDeactivateSelfError, UserNotFoundError


@dataclass(frozen=True, slots=True)
class SetUserActiveUseCase:
    """Alterna o acesso de uma conta; um admin não pode desativar a si mesmo."""

    users: UserRepository

    async def execute(
        self, *, acting_admin_id: UUID, user_id: UUID, is_active: bool
    ) -> User:
        if not is_active and acting_admin_id == user_id:
            raise CannotDeactivateSelfError

        user = await self.users.set_active(user_id=user_id, is_active=is_active)
        if user is None:
            raise UserNotFoundError

        return user
