"""Entidades de comunicação sem acoplamento a provedor de e-mail."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from crm_api.domain.documents.entities import DocumentStatus


@dataclass(frozen=True, slots=True)
class MessageTemplate:
    """Modelo mantido pelo proprietário; não representa uma mensagem enviada."""

    id: UUID
    name: str
    subject: str
    body: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise ValueError("message template id must be a UUID")
        for field_name, value in (
            ("name", self.name),
            ("subject", self.subject),
            ("body", self.body),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"message template {field_name} must not be blank")
        for timestamp in (self.created_at, self.updated_at):
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("message template timestamps must include a timezone")


@dataclass(frozen=True, slots=True)
class RecipientCandidate:
    """Cliente elegível por situação, sem expor endereço de e-mail."""

    client_id: UUID
    display_name: str
    document_status: DocumentStatus
    matching_documents: int

    def __post_init__(self) -> None:
        if not isinstance(self.client_id, UUID):
            raise ValueError("recipient candidate client_id must be a UUID")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("recipient candidate display_name must not be blank")
        if not isinstance(self.document_status, DocumentStatus):
            raise ValueError("recipient candidate document_status is invalid")
        if not isinstance(self.matching_documents, int) or self.matching_documents < 1:
            raise ValueError("recipient candidate matching_documents must be positive")
