"""Modelos SQLAlchemy do esquema de autenticação."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from crm_api.infrastructure.database import Base


class UserModel(Base):
    """Conta interna autorizada a acessar o CRM."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(unique=True, index=True)
    full_name: Mapped[str]
    password_hash: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    sessions: Mapped[list["SessionModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class SessionModel(Base):
    """Sessão de acesso emitida após autenticação bem-sucedida."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["UserModel"] = relationship(back_populates="sessions")


class OwnerSlotModel(Base):
    """Linha única cuja restrição de unicidade serializa a criação do proprietário.

    Substitui o ``pg_advisory_xact_lock`` específico do PostgreSQL: a violação
    de chave primária ao inserir ``id=1`` é atômica e bloqueante em qualquer
    dialeto suportado, então apenas uma requisição concorrente consegue
    persistir esta linha (ver ADR 0003 e ``SqlAlchemyUserRepository``).
    """

    __tablename__ = "owner_slot"

    id: Mapped[int] = mapped_column(primary_key=True)
