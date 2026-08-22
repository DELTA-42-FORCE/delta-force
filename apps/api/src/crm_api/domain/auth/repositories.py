"""Portas que a camada de aplicação usa sem conhecer o adaptador concreto."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from crm_api.domain.auth.entities import Session, User


class UserRepository(Protocol):
    """Consulta de contas internas por identificador de login."""

    async def find_by_email(self, email: str) -> User | None: ...

    async def find_by_id(self, user_id: UUID) -> User | None: ...

    async def has_any(self) -> bool: ...

    async def create_owner_if_none(
        self, *, email: str, full_name: str, password_hash: str
    ) -> User | None:
        """Cria o proprietário somente se nenhuma conta existir."""
        ...


class SessionRepository(Protocol):
    """Ciclo de vida das sessões emitidas no login."""

    async def create(
        self, *, token_hash: str, user_id: UUID, expires_at: datetime
    ) -> Session: ...

    async def find_by_token_hash(self, token_hash: str) -> Session | None: ...

    async def revoke_by_token_hash(self, token_hash: str) -> None: ...


class PasswordHasher(Protocol):
    """Verificação de senha sem expor o algoritmo escolhido ao domínio."""

    def hash(self, password: str) -> str: ...

    def verify(self, *, password: str, password_hash: str) -> bool: ...

    @property
    def dummy_hash(self) -> str:
        """Hash válido sem conta correspondente, usado para mitigar timing oracle."""
        ...


class SessionTokenHasher(Protocol):
    """Transforma tokens opacos antes de qualquer acesso à persistência."""

    def hash(self, token: str) -> str: ...
