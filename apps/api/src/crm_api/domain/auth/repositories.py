"""Portas que a camada de aplicação usa sem conhecer o adaptador concreto."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from crm_api.domain.auth.entities import Session, User


class UserRepository(Protocol):
    """Consulta e gestão de contas internas autorizadas."""

    async def find_by_email(self, email: str) -> User | None: ...

    async def find_by_id(self, user_id: UUID) -> User | None: ...

    async def list_all(self) -> list[User]: ...

    async def create(
        self,
        *,
        email: str,
        full_name: str,
        password_hash: str,
        is_admin: bool,
    ) -> User: ...

    async def update(
        self, *, user_id: UUID, full_name: str | None, is_admin: bool | None
    ) -> User | None: ...

    async def set_active(self, *, user_id: UUID, is_active: bool) -> User | None: ...


class SessionRepository(Protocol):
    """Ciclo de vida das sessões emitidas no login."""

    async def create(
        self, *, token: str, user_id: UUID, expires_at: datetime
    ) -> Session: ...

    async def find_by_token(self, token: str) -> Session | None: ...

    async def revoke(self, token: str) -> None: ...


class PasswordHasher(Protocol):
    """Hashing e verificação de senha sem expor o algoritmo ao domínio."""

    def hash(self, password: str) -> str: ...

    def verify(self, *, password: str, password_hash: str) -> bool: ...

    @property
    def dummy_hash(self) -> str:
        """Hash válido sem conta correspondente, usado para mitigar timing oracle."""
        ...
