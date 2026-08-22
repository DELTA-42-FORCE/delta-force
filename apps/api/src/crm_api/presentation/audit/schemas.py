"""Contratos públicos e sanitizados da consulta de auditoria."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditResourceType,
    AuditResult,
)


class AuditEventResponse(BaseModel):
    id: UUID
    occurred_at: datetime
    actor_kind: AuditActorKind
    actor_user_id: UUID | None
    action: AuditAction
    resource_type: AuditResourceType
    resource_id: str | None
    result: AuditResult
    context: dict[str, str]


class AuditEventCursorResponse(BaseModel):
    occurred_at: datetime
    id: UUID


class AuditEventListResponse(BaseModel):
    items: list[AuditEventResponse]
    limit: int = Field(ge=1, le=100)
    next_cursor: AuditEventCursorResponse | None
