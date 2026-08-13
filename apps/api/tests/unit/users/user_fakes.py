"""Fakes de infraestrutura usados pelos testes de gestão de usuários."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from crm_api.domain.auth.entities import User
from crm_api.domain.users.errors import EmailAlreadyRegisteredError


@dataclass
class FakeUserRepository:
    users: dict[UUID, User] = field(default_factory=dict)

    async def find_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    async def find_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def list_all(self) -> list[User]:
        return list(self.users.values())

    async def create(
        self, *, email: str, full_name: str, password_hash: str, is_admin: bool
    ) -> User:
        if await self.find_by_email(email) is not None:
            raise EmailAlreadyRegisteredError

        user = User(
            id=uuid4(),
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            is_active=True,
            is_admin=is_admin,
        )
        self.users[user.id] = user
        return user

    async def update(
        self, *, user_id: UUID, full_name: str | None, is_admin: bool | None
    ) -> User | None:
        user = self.users.get(user_id)
        if user is None:
            return None

        updated = User(
            id=user.id,
            email=user.email,
            full_name=full_name if full_name is not None else user.full_name,
            password_hash=user.password_hash,
            is_active=user.is_active,
            is_admin=is_admin if is_admin is not None else user.is_admin,
        )
        self.users[user_id] = updated
        return updated

    async def set_active(self, *, user_id: UUID, is_active: bool) -> User | None:
        user = self.users.get(user_id)
        if user is None:
            return None

        updated = User(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            password_hash=user.password_hash,
            is_active=is_active,
            is_admin=user.is_admin,
        )
        self.users[user_id] = updated
        return updated


class FakePasswordHasher:
    """Compara texto puro para evitar acoplar os testes ao bcrypt."""

    def hash(self, password: str) -> str:
        return password

    def verify(self, *, password: str, password_hash: str) -> bool:
        return password == password_hash

    @property
    def dummy_hash(self) -> str:
        return "unreachable-dummy-hash"
