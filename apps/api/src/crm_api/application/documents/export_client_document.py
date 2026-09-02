"""Exportação auditada de uma cópia de documento da área privada."""

from collections.abc import AsyncIterator
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
from crm_api.domain.documents.entities import StoredDocument
from crm_api.domain.documents.errors import DocumentContentUnavailableError
from crm_api.domain.documents.repositories import (
    DocumentMetadataRepository,
    DocumentStorage,
)


@dataclass(frozen=True, slots=True)
class DocumentExport:
    """Metadados e o fluxo já iniciado da cópia autorizada."""

    document: StoredDocument
    chunks: AsyncIterator[bytes]


@dataclass(frozen=True, slots=True)
class ExportClientDocumentUseCase:
    """Confirma que o arquivo é legível antes de auditar e devolver a cópia."""

    documents: DocumentMetadataRepository
    storage: DocumentStorage
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        client_folder_id: UUID,
        document_id: UUID,
    ) -> DocumentExport:
        document = await resolve_document_in_folder(
            self.documents,
            client_folder_id=client_folder_id,
            document_id=document_id,
        )

        stream = self.storage.open_stream(storage_key=document.storage_key)
        try:
            # O primeiro bloco é lido aqui para que um arquivo ausente ou
            # ilegível vire erro antes de a resposta começar a ser enviada.
            first_chunk = await anext(stream, b"")
        except DocumentContentUnavailableError:
            await self._record(
                actor_user_id=actor_user_id,
                document=document,
                result=AuditResult.FAILURE,
                reason_code="document_content_unavailable",
            )
            await self.transaction.commit()
            raise

        # O sucesso só é auditado quando o fluxo termina inteiro: se a leitura
        # falhar depois deste primeiro bloco, a resposta já começou, mas a
        # auditoria registra a falha em vez de um sucesso enganoso.
        return DocumentExport(
            document=document,
            chunks=self._audited_stream(
                actor_user_id=actor_user_id,
                document=document,
                first_chunk=first_chunk,
                rest=stream,
            ),
        )

    async def _audited_stream(
        self,
        *,
        actor_user_id: UUID,
        document: StoredDocument,
        first_chunk: bytes,
        rest: AsyncIterator[bytes],
    ) -> AsyncIterator[bytes]:
        try:
            if first_chunk:
                yield first_chunk
            async for chunk in rest:
                yield chunk
        except DocumentContentUnavailableError:
            await self._record(
                actor_user_id=actor_user_id,
                document=document,
                result=AuditResult.FAILURE,
                reason_code="document_content_unavailable",
            )
            await self.transaction.commit()
            raise
        else:
            await self._record(
                actor_user_id=actor_user_id,
                document=document,
                result=AuditResult.SUCCESS,
                reason_code=None,
            )
            await self.transaction.commit()

    async def _record(
        self,
        *,
        actor_user_id: UUID,
        document: StoredDocument,
        result: AuditResult,
        reason_code: str | None,
    ) -> None:
        await self.audit.execute(
            actor_kind=AuditActorKind.AUTHENTICATED,
            actor_user_id=actor_user_id,
            action=AuditAction.DOCUMENT_EXPORTED,
            resource_type=AuditResourceType.DOCUMENT,
            resource_id=str(document.id),
            result=result,
            context={} if reason_code is None else {"reason_code": reason_code},
        )
