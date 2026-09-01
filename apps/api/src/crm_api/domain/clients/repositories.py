"""Portas de persistência da pasta flexível de clientes."""

from typing import Mapping, Protocol

from crm_api.domain.clients.entities import ClientFolder


class ClientFolderRepository(Protocol):
    """Persiste pastas sem expor ORM ou dialeto de banco."""

    async def create(
        self, *, display_name: str, profile_data: Mapping[str, str]
    ) -> ClientFolder: ...
