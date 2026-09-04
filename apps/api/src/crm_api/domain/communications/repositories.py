"""Portas de persistência para comunicação ainda sem envio."""

from typing import Protocol
from uuid import UUID

from crm_api.domain.communications.entities import MessageTemplate, RecipientCandidate
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
        self, *, document_status: DocumentStatus, limit: int
    ) -> list[RecipientCandidate]: ...
