"""Edição transacional e auditada de uma pasta de cliente."""

from dataclasses import dataclass
from typing import Mapping
from uuid import UUID

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.clients.normalization import (
    normalize_display_name,
    normalize_profile_data,
)
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
class UpdateClientFolderUseCase:
    """Atualiza nome e dados flexíveis de uma pasta existente."""

    clients: ClientFolderRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        client_id: UUID,
        display_name: str,
        profile_data: Mapping[str, str] | None = None,
    ) -> ClientFolder:
        normalized_name = normalize_display_name(display_name)
        normalized_profile = normalize_profile_data(profile_data)

        client = await self.clients.update(
            id=client_id,
            display_name=normalized_name,
            profile_data=normalized_profile,
        )
        if client is None:
            raise ClientFolderNotFoundError

        try:
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.CLIENT_FOLDER_UPDATED,
                resource_type=AuditResourceType.CLIENT_FOLDER,
                resource_id=str(client.id),
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return client
