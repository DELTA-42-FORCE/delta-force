"""Criação transacional de uma pasta digital flexível de cliente."""

from dataclasses import dataclass
from typing import Mapping
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
        profile_data: Mapping[str, str] | None = None,
    ) -> ClientFolder:
        normalized_name = self._normalize_display_name(display_name)
        normalized_profile = self._normalize_profile_data(profile_data)
        try:
            client = await self.clients.create(
                display_name=normalized_name,
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

    @staticmethod
    def _normalize_display_name(value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("client folder display_name must be a string")
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("client folder display_name must not be blank")
        return normalized

    @staticmethod
    def _normalize_profile_data(
        value: Mapping[str, str] | None,
    ) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, Mapping) or any(
            not isinstance(key, str) or not isinstance(item, str)
            for key, item in value.items()
        ):
            raise ValueError("client folder profile_data must map strings to strings")
        return dict(value)
