"""Primeira configuração da conta única do proprietário."""

from dataclasses import dataclass

from crm_api.application.auth.authenticate_user import (
    AuthenticateUserUseCase,
    AuthenticationResult,
)
from crm_api.domain.auth.errors import SetupAlreadyCompletedError
from crm_api.domain.auth.repositories import PasswordHasher, UserRepository


@dataclass(frozen=True, slots=True)
class SetupOwnerUseCase:
    """Cria a única conta inicial e já inicia sua primeira sessão."""

    users: UserRepository
    password_hasher: PasswordHasher
    authenticate: AuthenticateUserUseCase

    async def execute(
        self, *, email: str, full_name: str, password: str
    ) -> AuthenticationResult:
        owner = await self.users.create_owner_if_none(
            email=email,
            full_name=full_name,
            password_hash=self.password_hasher.hash(password),
        )
        if owner is None:
            raise SetupAlreadyCompletedError

        return await self.authenticate.execute(email=email, password=password)


@dataclass(frozen=True, slots=True)
class GetSetupStatusUseCase:
    """Informa à interface se a primeira configuração ainda é necessária."""

    users: UserRepository

    async def execute(self) -> bool:
        return not await self.users.has_any()
