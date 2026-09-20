"""Portas de persistência para comunicação ainda sem envio."""

from typing import Protocol
from uuid import UUID

from crm_api.domain.communications.entities import (
    EmailDeliveryStatus,
    EmailDeliveryResult,
    EmailDispatch,
    EmailDispatchCursor,
    EmailSenderSettings,
    MessageTemplate,
    OutboundEmail,
    RecipientCandidate,
    RecipientCandidateCursor,
)
from crm_api.domain.documents.entities import DocumentStatus


class CommunicationRepository(Protocol):
    async def create_template(
        self, *, name: str, subject: str, body: str
    ) -> MessageTemplate: ...

    async def list_templates(self) -> list[MessageTemplate]: ...

    async def get_template(self, *, id: UUID) -> MessageTemplate | None: ...

    async def update_template(
        self, *, id: UUID, name: str, subject: str, body: str
    ) -> MessageTemplate | None: ...

    async def delete_template(self, *, id: UUID) -> bool: ...

    async def list_recipient_candidates(
        self,
        *,
        document_status: DocumentStatus,
        limit: int,
        before: RecipientCandidateCursor | None,
    ) -> list[RecipientCandidate]: ...

    async def get_sender_settings(self) -> EmailSenderSettings | None: ...

    async def save_sender_settings(
        self, *, settings: EmailSenderSettings
    ) -> EmailSenderSettings: ...

    async def create_dispatch(
        self,
        *,
        template_id: UUID,
        client_id: UUID,
        recipient_email: str | None,
        subject: str,
        body: str,
        message_id: str,
        status: EmailDeliveryStatus,
        detail: str | None,
    ) -> EmailDispatch: ...

    async def update_dispatch_result(
        self,
        *,
        id: UUID,
        status: EmailDeliveryStatus,
        detail: str | None,
    ) -> EmailDispatch: ...

    async def has_delivery_requiring_confirmation(
        self, *, template_id: UUID, client_id: UUID
    ) -> bool: ...

    async def list_dispatches(
        self, *, limit: int, before: EmailDispatchCursor | None
    ) -> list[EmailDispatch]: ...


class EmailSender(Protocol):
    async def send(
        self,
        *,
        settings: EmailSenderSettings,
        message: OutboundEmail,
        credential: str | None,
    ) -> EmailDeliveryResult: ...
