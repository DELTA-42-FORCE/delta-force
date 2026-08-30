"""Adaptador assíncrono de persistência (SQLite em arquivo e PostgreSQL legado)."""

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase

from crm_api.core.config import get_settings


class Base(DeclarativeBase):
    """Base declarativa para futuros modelos persistentes do CRM."""


def _configure_sqlite_connection(engine: AsyncEngine) -> None:
    """Alinha o driver SQLite ao modelo transacional do SQLAlchemy (ADR 0003)."""

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:
        del connection_record
        # Desliga o controle implícito de transação do pysqlite/aiosqlite para
        # que o SQLAlchemy decida quando abrir cada transação (ver evento "begin").
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=FULL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    @event.listens_for(engine.sync_engine, "begin")
    def _begin_sqlite_transaction(connection: Any) -> None:
        connection.exec_driver_sql("BEGIN")


@lru_cache
def get_engine() -> AsyncEngine:
    """Cria o engine compartilhado, sem conectar até ser necessário."""
    engine = create_async_engine(
        get_settings().database_url,
        pool_pre_ping=True,
    )
    if engine.dialect.name == "sqlite":
        _configure_sqlite_connection(engine)
    return engine


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
