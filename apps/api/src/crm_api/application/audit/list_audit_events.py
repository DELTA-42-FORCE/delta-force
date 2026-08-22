"""Caso de uso para consultar a trilha de auditoria."""

from dataclasses import dataclass
from uuid import UUID

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.transactions import Transaction
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditEvent,
    AuditEventCursor,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.audit.repositories import AuditEventRepository


@dataclass(frozen=True, slots=True)
class AuditEventPage:
    items: tuple[AuditEvent, ...]
    next_cursor: AuditEventCursor | None


@dataclass(frozen=True, slots=True)
class ListAuditEventsUseCase:
    """Consulta uma página estável e audita a visualização do log."""

    events: AuditEventRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        limit: int,
        before: AuditEventCursor | None,
        action: AuditAction | None = None,
        result: AuditResult | None = None,
    ) -> AuditEventPage:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if action is not None and not isinstance(action, AuditAction):
            raise ValueError("action filter is invalid")
        if result is not None and not isinstance(result, AuditResult):
            raise ValueError("result filter is invalid")

        try:
            events = await self.events.list_recent(
                limit=limit + 1,
                before=before,
                action=action,
                result=result,
            )
            page_items = tuple(events[:limit])
            next_cursor = (
                AuditEventCursor(
                    occurred_at=page_items[-1].occurred_at,
                    id=page_items[-1].id,
                )
                if len(events) > limit and page_items
                else None
            )
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.AUDIT_LOG_VIEW,
                resource_type=AuditResourceType.AUDIT_LOG,
                resource_id=None,
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise

        return AuditEventPage(items=page_items, next_cursor=next_cursor)
