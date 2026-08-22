"""Fakes de infraestrutura usados pelos testes de autenticação."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from crm_api.domain.audit.entities import (
    AuditAction,
    AuditEvent,
    AuditEventCursor,
    AuditResult,
)
from crm_api.domain.auth.entities import Session, User


@dataclass
class FakeUserRepository:
    users: dict[str, User] = field(default_factory=dict)

    async def find_by_email(self, email: str) -> User | None:
        return self.users.get(email)

    async def find_by_id(self, user_id: UUID) -> User | None:
        return next((u for u in self.users.values() if u.id == user_id), None)

    async def has_any(self) -> bool:
        return bool(self.users)

    async def create_owner_if_none(
        self, *, email: str, full_name: str, password_hash: str
    ) -> User | None:
        if self.users:
            return None
        user = User(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            is_active=True,
        )
        self.users[email] = user
        return user


@dataclass
class FakeSessionRepository:
    sessions: dict[str, Session] = field(default_factory=dict)

    async def create(
        self, *, token_hash: str, user_id: UUID, expires_at: datetime
    ) -> Session:
        session = Session(
            token_hash=token_hash,
            user_id=user_id,
            expires_at=expires_at,
            revoked_at=None,
        )
        self.sessions[token_hash] = session
        return session

    async def find_by_token_hash(self, token_hash: str) -> Session | None:
        return self.sessions.get(token_hash)

    async def revoke_by_token_hash(self, token_hash: str) -> None:
        session = self.sessions.get(token_hash)
        if session is None:
            return

        self.sessions[token_hash] = Session(
            token_hash=session.token_hash,
            user_id=session.user_id,
            expires_at=session.expires_at,
            revoked_at=datetime.now(UTC),
        )


class FakePasswordHasher:
    """Compara texto puro para evitar acoplar os testes ao bcrypt."""

    def hash(self, password: str) -> str:
        return password

    def verify(self, *, password: str, password_hash: str) -> bool:
        return password == password_hash

    @property
    def dummy_hash(self) -> str:
        return "unreachable-dummy-hash"


class FakeSessionTokenHasher:
    def hash(self, token: str) -> str:
        return f"hashed:{token}"


@dataclass
class FakeAuditEventRepository:
    events: list[AuditEvent] = field(default_factory=list)

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)

    async def list_recent(
        self,
        *,
        limit: int,
        before: AuditEventCursor | None,
        action: AuditAction | None,
        result: AuditResult | None,
    ) -> list[AuditEvent]:
        newest_first = sorted(
            self.events,
            key=lambda event: (event.occurred_at, event.id),
            reverse=True,
        )
        if before is not None:
            newest_first = [
                event
                for event in newest_first
                if (event.occurred_at, event.id) < (before.occurred_at, before.id)
            ]
        if action is not None:
            newest_first = [event for event in newest_first if event.action is action]
        if result is not None:
            newest_first = [event for event in newest_first if event.result is result]
        return newest_first[:limit]


@dataclass
class FakeTransaction:
    commit_calls: int = 0
    rollback_calls: int = 0

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1
