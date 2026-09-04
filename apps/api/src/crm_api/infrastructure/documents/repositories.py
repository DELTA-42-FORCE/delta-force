"""Adaptador SQLAlchemy da porta de metadados de documentos."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from crm_api.domain.documents.entities import (
    DocumentCursor,
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
        title=model.title,
        category=model.category,
        notes=model.notes,
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
        title: str | None,
        category: str | None,
        notes: str | None,
        content: StoredContent,
    ) -> StoredDocument:
        model = DocumentModel(
            id=id,
            client_folder_id=client_folder_id,
            original_filename=original_filename,
            title=title,
            category=category,
            notes=notes,
            storage_key=content.storage_key,
            media_type=content.media_type.value,
            byte_size=content.byte_size,
            checksum_sha256=content.checksum_sha256,
            # O instante vem da aplicação, como na trilha de auditoria: o
            # CURRENT_TIMESTAMP do SQLite tem resolução de segundo e outro
            # formato, o que empataria e desalinharia o cursor da paginação.
            stored_at=datetime.now(UTC),
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return _to_stored_document(model)

    async def get(self, *, id: UUID) -> StoredDocument | None:
        model = await self.session.get(DocumentModel, id)
        return _to_stored_document(model) if model is not None else None

    async def list_for_client(
        self,
        *,
        client_folder_id: UUID,
        limit: int,
        before: DocumentCursor | None,
    ) -> list[StoredDocument]:
        statement = select(DocumentModel).where(
            DocumentModel.client_folder_id == client_folder_id
        )
        if before is not None:
            # O cursor por (stored_at, id) impede que um anexo novo desloque
            # páginas já percorridas, como na trilha de auditoria.
            statement = statement.where(
                or_(
                    DocumentModel.stored_at < before.stored_at,
                    and_(
                        DocumentModel.stored_at == before.stored_at,
                        DocumentModel.id < before.id,
                    ),
                )
            )

        statement = statement.order_by(
            DocumentModel.stored_at.desc(),
            DocumentModel.id.desc(),
        ).limit(limit)
        models = (await self.session.scalars(statement)).all()
        return [_to_stored_document(model) for model in models]
