"""Renderização segura das variáveis homologadas dos modelos de mensagem."""

from dataclasses import dataclass
from uuid import UUID

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

    async def execute(self, *, template_id: UUID, client_id: UUID) -> RenderedMessage:
        template = await self.templates.get_template(id=template_id)
        if template is None:
            raise MessageTemplateNotFoundError
        client = await self.clients.get(id=client_id)
        if client is None:
            raise ClientFolderNotFoundError

        subject = template.subject.replace("{{nome}}", client.display_name)
        body = template.body.replace("{{nome}}", client.display_name)
        return RenderedMessage(client_id=client.id, subject=subject, body=body)
