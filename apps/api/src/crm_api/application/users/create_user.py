"""Caso de uso: administrador cadastra uma nova conta interna."""

from dataclasses import dataclass

from crm_api.domain.auth.entities import User
from crm_api.domain.auth.repositories import PasswordHasher, UserRepository
from crm_api.domain.users.errors import EmailAlreadyRegisteredError


@dataclass(frozen=True, slots=True)
class CreateUserUseCase:
    """Cria uma conta com senha inicial definida pelo administrador."""

    users: UserRepository
    password_hasher: PasswordHasher

    async def execute(
        self, *, email: str, full_name: str, password: str, is_admin: bool
    ) -> User:
        if await self.users.find_by_email(email) is not None:
            raise EmailAlreadyRegisteredError

        return await self.users.create(
            email=email,
            full_name=full_name,
            password_hash=self.password_hasher.hash(password),
            is_admin=is_admin,
        )
