"""Contratos públicos e sanitizados da pasta flexível de clientes."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ClientFolderResponse(BaseModel):
    id: UUID
    display_name: str
    profile_data: dict[str, str]
    created_at: datetime
    updated_at: datetime


class ClientFolderCursorResponse(BaseModel):
    display_name: str
    id: UUID


class ClientFolderListResponse(BaseModel):
    items: list[ClientFolderResponse]
    limit: int = Field(ge=1, le=100)
    next_cursor: ClientFolderCursorResponse | None


class CreateClientFolderRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    profile_data: dict[str, str] | None = None


class UpdateClientFolderRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    profile_data: dict[str, str] | None = None
