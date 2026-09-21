"""Criação transacional de uma pasta digital flexível de cliente."""

from dataclasses import dataclass
from typing import Mapping
from uuid import UUID

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.clients.normalization import (
    normalize_display_name,
    normalize_email,
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
from crm_api.domain.clients.repositories import ClientFolderRepository


@dataclass(frozen=True, slots=True)
class CreateClientFolderUseCase:
    """Cria uma pasta exigindo apenas o nome identificador do cliente."""

    clients: ClientFolderRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        display_name: str,
        email: str | None = None,
        profile_data: Mapping[str, str] | None = None,
    ) -> ClientFolder:
        normalized_name = normalize_display_name(display_name)
        normalized_email = normalize_email(email)
        normalized_profile = normalize_profile_data(profile_data)
        try:
            client = await self.clients.create(
                display_name=normalized_name,
                email=normalized_email,
                profile_data=normalized_profile,
            )
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.CLIENT_FOLDER_CREATED,
                resource_type=AuditResourceType.CLIENT_FOLDER,
                resource_id=str(client.id),
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return client
