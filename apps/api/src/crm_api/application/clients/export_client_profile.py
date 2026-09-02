"""Geração auditada da ficha cadastral do cliente em PDF (#34)."""

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
from crm_api.domain.clients.reporting import (
    ClientProfileDocument,
    ClientProfilePdfRenderer,
)
from crm_api.domain.clients.repositories import ClientFolderRepository


@dataclass(frozen=True, slots=True)
class ClientProfileExport:
    """Ficha renderizada e o nome de identificação usado para nomear o arquivo."""

    display_name: str
    pdf_bytes: bytes


@dataclass(frozen=True, slots=True)
class ExportClientProfileUseCase:
    """Renderiza a ficha da pasta existente e audita a exportação."""

    clients: ClientFolderRepository
    renderer: ClientProfilePdfRenderer
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self, *, actor_user_id: UUID, client_id: UUID
    ) -> ClientProfileExport:
        client = await self.clients.get(id=client_id)
        if client is None:
            raise ClientFolderNotFoundError

        document = ClientProfileDocument.from_folder(client)
        pdf_bytes = self.renderer.render(document)

        try:
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.CLIENT_FOLDER_PROFILE_EXPORTED,
                resource_type=AuditResourceType.CLIENT_FOLDER,
                resource_id=str(client.id),
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise

        return ClientProfileExport(
            display_name=client.display_name, pdf_bytes=pdf_bytes
        )
