"""Porta transacional compartilhada pelos casos de uso mutáveis."""

from typing import Protocol


class Transaction(Protocol):
    """Confirma ou desfaz uma unidade de trabalho da aplicação."""

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
