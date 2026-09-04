"""Contratos HTTP de modelos e seleção de candidatos."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from crm_api.domain.documents.entities import DocumentStatus


class MessageTemplatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20_000)


class MessageTemplateResponse(MessageTemplatePayload):
    id: UUID
    created_at: datetime
    updated_at: datetime


class RecipientCandidateResponse(BaseModel):
    client_id: UUID
    display_name: str
    document_status: DocumentStatus
    matching_documents: int = Field(ge=1)
