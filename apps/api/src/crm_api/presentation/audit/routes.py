"""Consulta autenticada da trilha append-only de auditoria."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from crm_api.application.audit.list_audit_events import ListAuditEventsUseCase
from crm_api.domain.audit.entities import AuditAction, AuditEventCursor, AuditResult
from crm_api.presentation.audit.dependencies import (
    get_list_audit_events_use_case,
)
from crm_api.presentation.audit.schemas import (
    AuditEventListResponse,
    AuditEventCursorResponse,
    AuditEventResponse,
)
from crm_api.presentation.auth.dependencies import CurrentUser

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=AuditEventListResponse)
async def list_audit_events(
    current_user: CurrentUser,
    use_case: Annotated[
        ListAuditEventsUseCase, Depends(get_list_audit_events_use_case)
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    action: Annotated[AuditAction | None, Query()] = None,
    result: Annotated[AuditResult | None, Query()] = None,
    before_occurred_at: Annotated[datetime | None, Query()] = None,
    before_id: Annotated[UUID | None, Query()] = None,
) -> AuditEventListResponse:
    if (before_occurred_at is None) != (before_id is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="before_occurred_at and before_id must be provided together",
        )
    try:
        cursor = (
            AuditEventCursor(occurred_at=before_occurred_at, id=before_id)
            if before_occurred_at is not None and before_id is not None
            else None
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="audit cursor is invalid",
        ) from None

    page = await use_case.execute(
        actor_user_id=current_user.id,
        limit=limit,
        before=cursor,
        action=action,
        result=result,
    )

    return AuditEventListResponse(
        items=[
            AuditEventResponse(
                id=event.id,
                occurred_at=event.occurred_at,
                actor_kind=event.actor_kind,
                actor_user_id=event.actor_user_id,
                action=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                result=event.result,
                context=dict(event.context),
            )
            for event in page.items
        ],
        limit=limit,
        next_cursor=(
            AuditEventCursorResponse(
                occurred_at=page.next_cursor.occurred_at,
                id=page.next_cursor.id,
            )
            if page.next_cursor is not None
            else None
        ),
    )
