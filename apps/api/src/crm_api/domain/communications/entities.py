"""Entidades de comunicação sem acoplamento a provedor de e-mail."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from crm_api.domain.documents.entities import DocumentStatus


@dataclass(frozen=True, slots=True)
class RecipientCandidateCursor:
    """Posição exclusiva e estável na seleção alfabética de candidatos."""

    display_name: str
    client_id: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.display_name, str) or not self.display_name:
            raise ValueError(
                "recipient candidate cursor display_name must not be blank"
            )
        if not isinstance(self.client_id, UUID):
            raise ValueError("recipient candidate cursor client_id must be a UUID")


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


class SmtpSecurity(StrEnum):
    STARTTLS = "starttls"
    TLS = "tls"
    NONE_DEV = "none_dev"


class EmailDeliveryStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    REJECTED = "rejected"
    UNKNOWN = "unknown"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    MISSING_EMAIL = "missing_email"


@dataclass(frozen=True, slots=True)
class EmailSenderSettings:
    sender_name: str
    sender_email: str
    smtp_host: str
    smtp_port: int
    security: SmtpSecurity
    username: str | None
    max_recipients: int


@dataclass(frozen=True, slots=True)
class OutboundEmail:
    message_id: str
    recipient: str
    subject: str
    body: str


@dataclass(frozen=True, slots=True)
class EmailDeliveryResult:
    status: EmailDeliveryStatus
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class EmailDispatch:
    id: UUID
    template_id: UUID
    client_id: UUID
    recipient_email: str | None
    subject: str
    body: str
    message_id: str
    retry_of_id: UUID | None
    retry_of_message_id: str | None
    status: EmailDeliveryStatus
    detail: str | None
    attempted_at: datetime


@dataclass(frozen=True, slots=True)
class EmailDispatchCursor:
    attempted_at: datetime
    id: UUID
