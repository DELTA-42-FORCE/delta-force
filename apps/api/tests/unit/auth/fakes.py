"""Fakes de infraestrutura usados pelos testes de autenticação."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from crm_api.domain.auth.entities import Session, User


@dataclass
class FakeUserRepository:
    users: dict[str, User] = field(default_factory=dict)

    async def find_by_email(self, email: str) -> User | None:
        return self.users.get(email)

    async def find_by_id(self, user_id: UUID) -> User | None:
        return next((u for u in self.users.values() if u.id == user_id), None)


@dataclass
class FakeSessionRepository:
    sessions: dict[str, Session] = field(default_factory=dict)

    async def create(
        self, *, token: str, user_id: UUID, expires_at: datetime
    ) -> Session:
        session = Session(
            token=token, user_id=user_id, expires_at=expires_at, revoked_at=None
        )
        self.sessions[token] = session
        return session

    async def find_by_token(self, token: str) -> Session | None:
        return self.sessions.get(token)

    async def revoke(self, token: str) -> None:
        session = self.sessions.get(token)
        if session is None:
            return

        self.sessions[token] = Session(
            token=session.token,
            user_id=session.user_id,
            expires_at=session.expires_at,
            revoked_at=datetime.now(UTC),
        )


class FakePasswordHasher:
    """Compara texto puro para evitar acoplar os testes ao bcrypt."""

    def verify(self, *, password: str, password_hash: str) -> bool:
        return password == password_hash

    @property
    def dummy_hash(self) -> str:
        return "unreachable-dummy-hash"
