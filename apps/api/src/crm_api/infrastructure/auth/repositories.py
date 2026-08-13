"""Adaptadores SQLAlchemy das portas de autenticação."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from crm_api.domain.auth.entities import Session, User
from crm_api.domain.users.errors import EmailAlreadyRegisteredError
from crm_api.infrastructure.auth.models import SessionModel, UserModel


def _to_user(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        full_name=model.full_name,
        password_hash=model.password_hash,
        is_active=model.is_active,
        is_admin=model.is_admin,
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

    async def list_all(self) -> list[User]:
        models = await self.session.scalars(
            select(UserModel).order_by(UserModel.created_at)
        )
        return [_to_user(model) for model in models]

    async def create(
        self,
        *,
        email: str,
        full_name: str,
        password_hash: str,
        is_admin: bool,
    ) -> User:
        model = UserModel(
            id=uuid.uuid4(),
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            is_admin=is_admin,
        )
        self.session.add(model)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise EmailAlreadyRegisteredError from None
        return _to_user(model)

    async def update(
        self, *, user_id: UUID, full_name: str | None, is_admin: bool | None
    ) -> User | None:
        model = await self.session.get(UserModel, user_id)
        if model is None:
            return None

        if full_name is not None:
            model.full_name = full_name
        if is_admin is not None:
            model.is_admin = is_admin

        await self.session.commit()
        return _to_user(model)

    async def set_active(self, *, user_id: UUID, is_active: bool) -> User | None:
        model = await self.session.get(UserModel, user_id)
        if model is None:
            return None

        model.is_active = is_active
        await self.session.commit()
        return _to_user(model)


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
