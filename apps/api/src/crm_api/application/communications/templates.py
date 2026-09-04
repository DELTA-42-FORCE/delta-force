"""Manutenção transacional e auditada de modelos de mensagem."""

from dataclasses import dataclass
from uuid import UUID

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.transactions import Transaction
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.communications.entities import MessageTemplate
from crm_api.domain.communications.errors import MessageTemplateNotFoundError
from crm_api.domain.communications.repositories import CommunicationRepository


def normalize_template_fields(
    *, name: str, subject: str, body: str
) -> tuple[str, str, str]:
    values = {"name": name, "subject": subject, "body": body}
    limits = {"name": 120, "subject": 200, "body": 20_000}
    normalized: dict[str, str] = {}
    for field_name, value in values.items():
        if not isinstance(value, str):
            raise ValueError(f"message template {field_name} must be a string")
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"message template {field_name} must not be blank")
        if len(cleaned) > limits[field_name]:
            raise ValueError(f"message template {field_name} is too long")
        normalized[field_name] = cleaned
    return normalized["name"], normalized["subject"], normalized["body"]


@dataclass(frozen=True, slots=True)
class CreateMessageTemplateUseCase:
    repository: CommunicationRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self, *, actor_user_id: UUID, name: str, subject: str, body: str
    ) -> MessageTemplate:
        normalized = normalize_template_fields(name=name, subject=subject, body=body)
        try:
            template = await self.repository.create_template(
                name=normalized[0], subject=normalized[1], body=normalized[2]
            )
            await self._record(
                actor_user_id, AuditAction.MESSAGE_TEMPLATE_CREATED, template.id
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return template

    async def _record(
        self, actor_user_id: UUID, action: AuditAction, resource_id: UUID
    ) -> None:
        await self.audit.execute(
            actor_kind=AuditActorKind.AUTHENTICATED,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=AuditResourceType.MESSAGE_TEMPLATE,
            resource_id=str(resource_id),
            result=AuditResult.SUCCESS,
        )


@dataclass(frozen=True, slots=True)
class ListMessageTemplatesUseCase:
    repository: CommunicationRepository

    async def execute(self) -> list[MessageTemplate]:
        return await self.repository.list_templates()


@dataclass(frozen=True, slots=True)
class UpdateMessageTemplateUseCase:
    repository: CommunicationRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        template_id: UUID,
        name: str,
        subject: str,
        body: str,
    ) -> MessageTemplate:
        normalized = normalize_template_fields(name=name, subject=subject, body=body)
        try:
            template = await self.repository.update_template(
                id=template_id,
                name=normalized[0],
                subject=normalized[1],
                body=normalized[2],
            )
            if template is None:
                raise MessageTemplateNotFoundError
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.MESSAGE_TEMPLATE_UPDATED,
                resource_type=AuditResourceType.MESSAGE_TEMPLATE,
                resource_id=str(template.id),
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return template


@dataclass(frozen=True, slots=True)
class DeleteMessageTemplateUseCase:
    repository: CommunicationRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(self, *, actor_user_id: UUID, template_id: UUID) -> None:
        try:
            deleted = await self.repository.delete_template(id=template_id)
            if not deleted:
                raise MessageTemplateNotFoundError
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.MESSAGE_TEMPLATE_DELETED,
                resource_type=AuditResourceType.MESSAGE_TEMPLATE,
                resource_id=str(template_id),
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
