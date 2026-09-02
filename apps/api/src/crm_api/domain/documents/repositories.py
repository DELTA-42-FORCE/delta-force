"""Portas de metadados e de armazenamento privado de documentos."""

from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID

from crm_api.domain.documents.entities import StoredContent, StoredDocument


class DocumentMetadataRepository(Protocol):
    """Persiste somente metadados; o binário permanece fora do banco."""

    async def add(
        self,
        *,
        id: UUID,
        client_folder_id: UUID,
        original_filename: str,
        content: StoredContent,
    ) -> StoredDocument: ...

    async def get(self, *, id: UUID) -> StoredDocument | None: ...


class DocumentStorage(Protocol):
    """Grava e descarta arquivos sem expor caminho absoluto nem URL pública."""

    async def store(
        self,
        *,
        document_id: UUID,
        original_filename: str,
        chunks: AsyncIterator[bytes],
    ) -> StoredContent: ...

    async def discard(self, *, storage_key: str) -> None: ...
