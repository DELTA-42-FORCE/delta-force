"""Adaptador SQLAlchemy da porta de metadados de documentos."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from crm_api.domain.documents.entities import (
    DocumentMediaType,
    StoredContent,
    StoredDocument,
)
from crm_api.infrastructure.documents.models import DocumentModel
from crm_api.infrastructure.timestamps import as_utc


def _to_stored_document(model: DocumentModel) -> StoredDocument:
    return StoredDocument(
        id=model.id,
        client_folder_id=model.client_folder_id,
        original_filename=model.original_filename,
        storage_key=model.storage_key,
        media_type=DocumentMediaType(model.media_type),
        byte_size=model.byte_size,
        checksum_sha256=model.checksum_sha256,
        stored_at=as_utc(model.stored_at),
    )


@dataclass(frozen=True, slots=True)
class SqlAlchemyDocumentMetadataRepository:
    """Persiste apenas metadados: nome, formato, tamanho, checksum e localização."""

    session: AsyncSession

    async def add(
        self,
        *,
        id: UUID,
        client_folder_id: UUID,
        original_filename: str,
        content: StoredContent,
    ) -> StoredDocument:
        model = DocumentModel(
            id=id,
            client_folder_id=client_folder_id,
            original_filename=original_filename,
            storage_key=content.storage_key,
            media_type=content.media_type.value,
            byte_size=content.byte_size,
            checksum_sha256=content.checksum_sha256,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return _to_stored_document(model)

    async def get(self, *, id: UUID) -> StoredDocument | None:
        model = await self.session.get(DocumentModel, id)
        return _to_stored_document(model) if model is not None else None
