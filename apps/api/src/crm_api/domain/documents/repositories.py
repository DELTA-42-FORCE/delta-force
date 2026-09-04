"""Portas de metadados e de armazenamento privado de documentos."""

from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID

from crm_api.domain.documents.entities import (
    DocumentCursor,
    StoredContent,
    StoredDocument,
)


class DocumentMetadataRepository(Protocol):
    """Persiste somente metadados; o binário permanece fora do banco."""

    async def add(
        self,
        *,
        id: UUID,
        client_folder_id: UUID,
        original_filename: str,
        title: str | None,
        category: str | None,
        notes: str | None,
        content: StoredContent,
    ) -> StoredDocument: ...

    async def get(self, *, id: UUID) -> StoredDocument | None: ...

    async def list_for_client(
        self,
        *,
        client_folder_id: UUID,
        limit: int,
        before: DocumentCursor | None,
    ) -> list[StoredDocument]: ...

    async def checksum_exists(
        self, *, client_folder_id: UUID, checksum_sha256: str
    ) -> bool: ...


class DocumentStorage(Protocol):
    """Grava, lê e descarta arquivos sem expor caminho absoluto nem URL pública."""

    async def store(
        self,
        *,
        document_id: UUID,
        original_filename: str,
        chunks: AsyncIterator[bytes],
    ) -> StoredContent: ...

    def open_stream(self, *, storage_key: str) -> AsyncIterator[bytes]: ...

    async def discard(self, *, storage_key: str) -> None: ...
