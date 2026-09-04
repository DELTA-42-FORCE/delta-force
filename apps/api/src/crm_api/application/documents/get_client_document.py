"""Consulta auditada de um documento pertencente a uma pasta de cliente."""

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
from crm_api.domain.documents.entities import StoredDocument
from crm_api.domain.documents.errors import DocumentNotFoundError
from crm_api.domain.documents.repositories import DocumentMetadataRepository


async def resolve_document_in_folder(
    documents: DocumentMetadataRepository,
    *,
    client_folder_id: UUID,
    document_id: UUID,
) -> StoredDocument:
    """Recusa acesso a documento de outra pasta com o mesmo erro de inexistente.

    O documento só é alcançável pela pasta a que pertence; responder de forma
    distinta revelaria a existência de anexos de outro cliente.
    """
    document = await documents.get(id=document_id)
    if document is None or document.client_folder_id != client_folder_id:
        raise DocumentNotFoundError(str(document_id))
    return document


@dataclass(frozen=True, slots=True)
class GetClientDocumentUseCase:
    """Devolve os metadados de um anexo e audita a consulta."""

    documents: DocumentMetadataRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        client_folder_id: UUID,
        document_id: UUID,
    ) -> StoredDocument:
        document = await resolve_document_in_folder(
            self.documents,
            client_folder_id=client_folder_id,
            document_id=document_id,
        )

        try:
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.DOCUMENT_VIEWED,
                resource_type=AuditResourceType.DOCUMENT,
                resource_id=str(document.id),
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return document
