"""Gravação transacional de um documento na área privada do proprietário."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID, uuid4

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.documents.normalization import (
    normalize_category,
    normalize_notes,
    normalize_title,
)
from crm_api.application.transactions import Transaction
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.clients.errors import ClientFolderNotFoundError
from crm_api.domain.clients.repositories import ClientFolderRepository
from crm_api.domain.documents.entities import StoredDocument
from crm_api.domain.documents.naming import normalize_document_filename
from crm_api.domain.documents.repositories import (
    DocumentMetadataRepository,
    DocumentStorage,
)


@dataclass(frozen=True, slots=True)
class StoreDocumentUseCase:
    """Publica o arquivo e os metadados como uma unidade auditada e reversível."""

    clients: ClientFolderRepository
    documents: DocumentMetadataRepository
    storage: DocumentStorage
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        client_folder_id: UUID,
        original_filename: str,
        chunks: AsyncIterator[bytes],
        title: str | None = None,
        category: str | None = None,
        notes: str | None = None,
    ) -> StoredDocument:
        # O nome é normalizado uma única vez na borda: o arquivo e os metadados
        # precisam guardar exatamente o mesmo valor, senão a validação de nome
        # não valeria para o texto que será exibido e consultado.
        filename = normalize_document_filename(original_filename)

        # As anotações também são validadas antes da gravação: um título
        # inválido não deve custar uma escrita em disco descartada em seguida.
        normalized_title = normalize_title(title)
        normalized_category = normalize_category(category)
        normalized_notes = normalize_notes(notes)

        # A pasta é confirmada antes da gravação para que um destino inexistente
        # não chegue a consumir espaço em disco.
        if await self.clients.get(id=client_folder_id) is None:
            raise ClientFolderNotFoundError(str(client_folder_id))

        document_id = uuid4()
        content = await self.storage.store(
            document_id=document_id,
            original_filename=filename,
            chunks=chunks,
        )
        try:
            document = await self.documents.add(
                id=document_id,
                client_folder_id=client_folder_id,
                original_filename=filename,
                title=normalized_title,
                category=normalized_category,
                notes=normalized_notes,
                content=content,
            )
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.DOCUMENT_STORED,
                resource_type=AuditResourceType.DOCUMENT,
                resource_id=str(document.id),
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except BaseException:
            # BaseException, e não Exception: `asyncio.CancelledError` não herda
            # de Exception, e um cancelamento entre a publicação e o commit
            # deixaria o arquivo órfão. Sem metadados ele seria inalcançável
            # pelo CRM e invisível para o backup da #44, então é removido junto
            # do rollback — a mesma garantia aplicada na camada de storage.
            await self.transaction.rollback()
            await self.storage.discard(storage_key=content.storage_key)
            raise
        return document
