"""Contratos públicos e sanitizados dos documentos de uma pasta de cliente.

A chave interna do arquivo nunca é exposta: o cliente HTTP só conhece o
identificador do documento e o consome pela rota autenticada de conteúdo.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from crm_api.domain.documents.entities import DocumentStatus


class DocumentResponse(BaseModel):
    id: UUID
    client_folder_id: UUID
    original_filename: str
    media_type: str
    byte_size: int
    checksum_sha256: str
    stored_at: datetime
    title: str | None
    category: str | None
    notes: str | None
    status: DocumentStatus


class UpdateDocumentStatusRequest(BaseModel):
    status: DocumentStatus


class DocumentCursorResponse(BaseModel):
    stored_at: datetime
    id: UUID


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    limit: int = Field(ge=1, le=100)
    next_cursor: DocumentCursorResponse | None
