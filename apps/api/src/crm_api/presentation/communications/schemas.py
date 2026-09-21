"""Contratos HTTP de modelos e seleção de candidatos."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, SecretStr

from crm_api.domain.communications.entities import EmailDeliveryStatus, SmtpSecurity
from crm_api.domain.documents.entities import DocumentStatus


class MessageTemplatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20_000)


class MessageTemplateResponse(MessageTemplatePayload):
    id: UUID
    created_at: datetime
    updated_at: datetime


class MessageTemplatePreviewRequest(BaseModel):
    client_id: UUID


class MessageTemplatePreviewResponse(BaseModel):
    client_id: UUID
    subject: str
    body: str


class RecipientCandidateResponse(BaseModel):
    client_id: UUID
    display_name: str
    document_status: DocumentStatus
    matching_documents: int = Field(ge=1)


class RecipientCandidateCursorResponse(BaseModel):
    display_name: str
    client_id: UUID


class RecipientCandidateListResponse(BaseModel):
    items: list[RecipientCandidateResponse]
    limit: int = Field(ge=1, le=100)
    next_cursor: RecipientCandidateCursorResponse | None


class EmailSenderSettingsPayload(BaseModel):
    sender_name: str = Field(min_length=1, max_length=120)
    sender_email: EmailStr
    smtp_host: str = Field(min_length=1, max_length=253)
    smtp_port: int = Field(ge=1, le=65535)
    security: SmtpSecurity
    username: str | None = Field(default=None, max_length=320)
    max_recipients: int = Field(default=50, ge=1, le=100)


class EmailSenderSettingsResponse(EmailSenderSettingsPayload):
    pass


class SendEmailBatchRequest(BaseModel):
    template_id: UUID
    client_ids: list[UUID] = Field(min_length=1, max_length=100)
    credential: SecretStr | None = None
    confirm_repeat: bool = False


class EmailDispatchResponse(BaseModel):
    id: UUID
    template_id: UUID
    client_id: UUID
    recipient_email: EmailStr | None
    subject: str
    body: str
    message_id: str
    status: EmailDeliveryStatus
    detail: str | None
    retry_of: UUID | None
    attempted_at: datetime


class EmailDispatchCursorResponse(BaseModel):
    attempted_at: datetime
    id: UUID


class EmailDispatchListResponse(BaseModel):
    items: list[EmailDispatchResponse]
    limit: int = Field(ge=1, le=100)
    next_cursor: EmailDispatchCursorResponse | None
