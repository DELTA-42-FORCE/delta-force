"""Consulta auditada de uma pasta de cliente por identificador."""

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
from crm_api.domain.clients.entities import ClientFolder
from crm_api.domain.clients.errors import ClientFolderNotFoundError
from crm_api.domain.clients.repositories import ClientFolderRepository


@dataclass(frozen=True, slots=True)
class GetClientFolderUseCase:
    """Consulta uma pasta existente e audita a visualização."""

    clients: ClientFolderRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(self, *, actor_user_id: UUID, client_id: UUID) -> ClientFolder:
        client = await self.clients.get(id=client_id)
        if client is None:
            raise ClientFolderNotFoundError

        try:
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.CLIENT_FOLDER_VIEWED,
                resource_type=AuditResourceType.CLIENT_FOLDER,
                resource_id=str(client.id),
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return client
