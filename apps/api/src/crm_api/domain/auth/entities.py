"""Entidades de autenticação, livres de HTTP e ORM."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class User:
    """Conta interna autorizada a acessar o CRM."""

    id: UUID
    email: str
    full_name: str
    password_hash: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class Session:
    """Sessão de acesso emitida após autenticação bem-sucedida."""

    token: str
    user_id: UUID
    expires_at: datetime
    revoked_at: datetime | None

    def is_valid(self, *, now: datetime) -> bool:
        """Uma sessão só é válida enquanto não expirada nem revogada."""
        return self.revoked_at is None and now < self.expires_at
