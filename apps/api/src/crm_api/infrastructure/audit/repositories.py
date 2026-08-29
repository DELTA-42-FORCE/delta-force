"""Adaptador SQLAlchemy da porta de auditoria."""

from dataclasses import dataclass

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditEvent,
    AuditEventCursor,
    AuditResourceType,
    AuditResult,
)
from crm_api.infrastructure.audit.models import AuditEventModel
from crm_api.infrastructure.timestamps import as_utc


def _to_event(model: AuditEventModel) -> AuditEvent:
    return AuditEvent(
        id=model.id,
        occurred_at=as_utc(model.occurred_at),
        actor_kind=AuditActorKind(model.actor_kind),
        actor_user_id=model.actor_user_id,
        action=AuditAction(model.action),
        resource_type=AuditResourceType(model.resource_type),
        resource_id=model.resource_id,
        result=AuditResult(model.result),
        context=dict(model.context),
    )


@dataclass(frozen=True, slots=True)
class SqlAlchemyAuditEventRepository:
    """Persiste eventos sem controlar a transação que os contém."""

    session: AsyncSession

    async def append(self, event: AuditEvent) -> None:
        self.session.add(
            AuditEventModel(
                id=event.id,
                occurred_at=event.occurred_at,
                actor_kind=event.actor_kind.value,
                actor_user_id=event.actor_user_id,
                action=event.action.value,
                resource_type=event.resource_type.value,
                resource_id=event.resource_id,
                result=event.result.value,
                context=dict(event.context),
            )
        )
        await self.session.flush()

    async def list_recent(
        self,
        *,
        limit: int,
        before: AuditEventCursor | None,
        action: AuditAction | None,
        result: AuditResult | None,
    ) -> list[AuditEvent]:
        statement = select(AuditEventModel)
        if action is not None:
            statement = statement.where(AuditEventModel.action == action.value)
        if result is not None:
            statement = statement.where(AuditEventModel.result == result.value)
        if before is not None:
            statement = statement.where(
                or_(
                    AuditEventModel.occurred_at < before.occurred_at,
                    and_(
                        AuditEventModel.occurred_at == before.occurred_at,
                        AuditEventModel.id < before.id,
                    ),
                )
            )

        statement = statement.order_by(
            AuditEventModel.occurred_at.desc(),
            AuditEventModel.id.desc(),
        ).limit(limit)
        models = (await self.session.scalars(statement)).all()
        return [_to_event(model) for model in models]
