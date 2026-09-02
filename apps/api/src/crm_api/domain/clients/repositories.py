"""Portas de persistência da pasta flexível de clientes."""

from typing import Mapping, Protocol
from uuid import UUID

from crm_api.domain.clients.entities import ClientFolder, ClientFolderCursor


class ClientFolderRepository(Protocol):
    """Persiste pastas sem expor ORM ou dialeto de banco."""

    async def create(
        self, *, display_name: str, profile_data: Mapping[str, str]
    ) -> ClientFolder: ...

    async def get(self, *, id: UUID) -> ClientFolder | None: ...

    async def find_by_display_name(
        self, *, display_name: str
    ) -> list[ClientFolder]: ...

    async def search(
        self,
        *,
        query: str | None,
        limit: int,
        before: ClientFolderCursor | None,
    ) -> list[ClientFolder]: ...

    async def update(
        self, *, id: UUID, display_name: str, profile_data: Mapping[str, str]
    ) -> ClientFolder | None: ...
