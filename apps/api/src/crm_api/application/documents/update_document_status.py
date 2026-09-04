"""Atualização auditada da situação de acompanhamento de um documento."""

from dataclasses import dataclass
from uuid import UUID

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.documents.get_client_document import (
    resolve_document_in_folder,
)
from crm_api.application.transactions import Transaction
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.documents.entities import DocumentStatus, StoredDocument
from crm_api.domain.documents.errors import DocumentNotFoundError
from crm_api.domain.documents.repositories import DocumentMetadataRepository


@dataclass(frozen=True, slots=True)
class UpdateDocumentStatusUseCase:
    """Altera somente o status; nenhuma situação bloqueia os demais fluxos."""

    documents: DocumentMetadataRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        client_folder_id: UUID,
        document_id: UUID,
        status: DocumentStatus,
    ) -> StoredDocument:
        if not isinstance(status, DocumentStatus):
            raise ValueError("document status is invalid")

        current = await resolve_document_in_folder(
            self.documents,
            client_folder_id=client_folder_id,
            document_id=document_id,
        )
        if current.status is status:
            return current

        try:
            updated = await self.documents.update_status(id=document_id, status=status)
            if updated is None:
                raise DocumentNotFoundError(str(document_id))
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.DOCUMENT_STATUS_UPDATED,
                resource_type=AuditResourceType.DOCUMENT,
                resource_id=str(document_id),
                result=AuditResult.SUCCESS,
                context={
                    "previous_status": current.status.value,
                    "new_status": status.value,
                },
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return updated
