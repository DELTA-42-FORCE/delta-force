"""Consulta auditada dos documentos anexados a uma pasta de cliente."""

from dataclasses import dataclass
from uuid import UUID

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.transactions import Transaction
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.clients.errors import ClientFolderNotFoundError
from crm_api.domain.clients.repositories import ClientFolderRepository
from crm_api.domain.documents.entities import DocumentCursor, StoredDocument
from crm_api.domain.documents.repositories import DocumentMetadataRepository


@dataclass(frozen=True, slots=True)
class ClientDocumentPage:
    items: tuple[StoredDocument, ...]
    next_cursor: DocumentCursor | None


@dataclass(frozen=True, slots=True)
class ListClientDocumentsUseCase:
    """Lista uma página estável dos anexos e audita a consulta."""

    clients: ClientFolderRepository
    documents: DocumentMetadataRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        client_folder_id: UUID,
        limit: int,
        before: DocumentCursor | None,
    ) -> ClientDocumentPage:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if await self.clients.get(id=client_folder_id) is None:
            raise ClientFolderNotFoundError(str(client_folder_id))

        try:
            documents = await self.documents.list_for_client(
                client_folder_id=client_folder_id,
                limit=limit + 1,
                before=before,
            )
            page_items = tuple(documents[:limit])
            next_cursor = (
                DocumentCursor(
                    stored_at=page_items[-1].stored_at,
                    id=page_items[-1].id,
                )
                if len(documents) > limit and page_items
                else None
            )
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.DOCUMENT_VIEWED,
                resource_type=AuditResourceType.DOCUMENT,
                resource_id=None,
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise

        return ClientDocumentPage(items=page_items, next_cursor=next_cursor)
