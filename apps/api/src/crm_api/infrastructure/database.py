"""Adaptador assíncrono de persistência PostgreSQL."""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase

from crm_api.core.config import get_settings


class Base(DeclarativeBase):
    """Base declarativa para futuros modelos persistentes do CRM."""


@lru_cache
def get_engine() -> AsyncEngine:
    """Cria o engine compartilhado, sem conectar até ser necessário."""
    return create_async_engine(
        get_settings().database_url,
        pool_pre_ping=True,
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Centraliza a criação de sessões para casos de uso e rotas."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_database_session() -> AsyncIterator[AsyncSession]:
    """Fornece uma sessão transacional sem acoplar rotas ao banco."""
    async with get_session_factory()() as session:
        yield session


async def check_database_connection() -> None:
    """Executa uma consulta mínima usada somente pelo endpoint de prontidão."""
    async with get_engine().connect() as connection:
        await connection.execute(text("SELECT 1"))
