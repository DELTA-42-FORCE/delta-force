"""Adaptadores SQLAlchemy das portas de autenticação."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
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
        token=model.token,
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


@dataclass(frozen=True, slots=True)
class SqlAlchemySessionRepository:
    """Gerencia o ciclo de vida das sessões de acesso no PostgreSQL."""

    session: AsyncSession

    async def create(
        self, *, token: str, user_id: UUID, expires_at: datetime
    ) -> Session:
        model = SessionModel(token=token, user_id=user_id, expires_at=expires_at)
        self.session.add(model)
        await self.session.commit()
        return _to_session(model)

    async def find_by_token(self, token: str) -> Session | None:
        model = await self.session.get(SessionModel, token)
        return _to_session(model) if model is not None else None

    async def revoke(self, token: str) -> None:
        model = await self.session.get(SessionModel, token)
        if model is None or model.revoked_at is not None:
            return

        model.revoked_at = datetime.now(UTC)
        await self.session.commit()
