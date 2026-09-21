"""Renderização segura das variáveis homologadas dos modelos de mensagem."""

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
from crm_api.domain.communications.errors import MessageTemplateNotFoundError
from crm_api.domain.communications.repositories import CommunicationRepository


@dataclass(frozen=True, slots=True)
class RenderedMessage:
    client_id: UUID
    subject: str
    body: str


@dataclass(frozen=True, slots=True)
class RenderMessageTemplateUseCase:
    templates: CommunicationRepository
    clients: ClientFolderRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self, *, actor_user_id: UUID, template_id: UUID, client_id: UUID
    ) -> RenderedMessage:
        try:
            template = await self.templates.get_template(id=template_id)
            if template is None:
                raise MessageTemplateNotFoundError
            client = await self.clients.get(id=client_id)
            if client is None:
                raise ClientFolderNotFoundError

            subject = template.subject.replace("{{nome}}", client.display_name)
            body = template.body.replace("{{nome}}", client.display_name)
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
        return RenderedMessage(client_id=client.id, subject=subject, body=body)
