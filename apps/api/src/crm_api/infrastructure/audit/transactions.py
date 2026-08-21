"""Fronteira transacional SQLAlchemy usada pelos casos de uso."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class SqlAlchemyTransaction:
    """Expõe commit e rollback sem vazar a sessão para a aplicação."""

    session: AsyncSession

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
