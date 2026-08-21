"""Adaptadores SQLAlchemy das portas de autenticação."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from crm_api.domain.auth.entities import Session, User
from crm_api.infrastructure.auth.models import SessionModel, UserModel


def _to_user(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        full_name=model.full_name,
        password_hash=model.password_hash,
        is_active=model.is_active,
    )


def _to_session(model: SessionModel) -> Session:
    return Session(
        token_hash=model.token_hash,
        user_id=model.user_id,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
    )


@dataclass(frozen=True, slots=True)
class SqlAlchemyUserRepository:
    """Consulta usuários internos persistidos no PostgreSQL."""

    session: AsyncSession

    async def find_by_email(self, email: str) -> User | None:
        model = await self.session.scalar(
            select(UserModel).where(UserModel.email == email)
        )
        return _to_user(model) if model is not None else None

    async def find_by_id(self, user_id: UUID) -> User | None:
        model = await self.session.get(UserModel, user_id)
        return _to_user(model) if model is not None else None

    async def has_any(self) -> bool:
        return bool(await self.session.scalar(select(func.count(UserModel.id))))

    async def create_owner_if_none(
        self, *, email: str, full_name: str, password_hash: str
    ) -> User | None:
        # Serializa somente o curto fluxo de primeira configuração. A trava é
        # transacional e impede duas requisições simultâneas de criarem contas.
        await self.session.execute(text("SELECT pg_advisory_xact_lock(1420015)"))
        if await self.has_any():
            return None

        model = UserModel(
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            is_active=True,
        )
        self.session.add(model)
        await self.session.flush()
        return _to_user(model)


@dataclass(frozen=True, slots=True)
class SqlAlchemySessionRepository:
    """Gerencia o ciclo de vida das sessões de acesso no PostgreSQL."""

    session: AsyncSession

    async def create(
        self, *, token_hash: str, user_id: UUID, expires_at: datetime
    ) -> Session:
        model = SessionModel(
            token_hash=token_hash, user_id=user_id, expires_at=expires_at
        )
        self.session.add(model)
        await self.session.flush()
        return _to_session(model)

    async def find_by_token_hash(self, token_hash: str) -> Session | None:
        model = await self.session.get(SessionModel, token_hash)
        return _to_session(model) if model is not None else None

    async def revoke_by_token_hash(self, token_hash: str) -> None:
        model = await self.session.get(SessionModel, token_hash)
        if model is None or model.revoked_at is not None:
            return

        model.revoked_at = datetime.now(UTC)
        await self.session.flush()
