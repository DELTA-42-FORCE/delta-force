"""Caso de uso para registrar uma ação relevante na trilha de auditoria."""

from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import Mapping
from uuid import UUID, uuid4

from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditEvent,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.audit.repositories import AuditEventRepository

_ALLOWED_CONTEXT_KEYS = frozenset({"route_template", "http_method", "reason_code"})
_ALLOWED_HTTP_METHODS = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
)
_ALLOWED_REASON_CODES = frozenset(
    {"invalid_credentials", "invalid_session", "setup_already_completed"}
)
_ROUTE_TEMPLATE_PATTERN = re.compile(r"^/[A-Za-z0-9_./{}-]{0,127}$")


@dataclass(frozen=True, slots=True)
class RecordAuditEventUseCase:
    """Valida e acrescenta um evento, sem controlar a transação externa."""

    events: AuditEventRepository

    async def execute(
        self,
        *,
        actor_kind: AuditActorKind,
        actor_user_id: UUID | None,
        action: AuditAction,
        resource_type: AuditResourceType,
        resource_id: str | None,
        result: AuditResult,
        context: Mapping[str, str] | None = None,
    ) -> AuditEvent:
        self._validate_actor(actor_kind=actor_kind, actor_user_id=actor_user_id)
        if not isinstance(action, AuditAction):
            raise ValueError("action is invalid")
        if not isinstance(resource_type, AuditResourceType):
            raise ValueError("resource_type is invalid")
        if not isinstance(result, AuditResult):
            raise ValueError("result is invalid")
        if resource_id is not None:
            self._validate_resource_id(resource_id)

        event_context = {} if context is None else dict(context)
        if any(key not in _ALLOWED_CONTEXT_KEYS for key in event_context):
            raise ValueError("context contains a non-allowlisted key")
        self._validate_context_values(event_context)

        event = AuditEvent(
            id=uuid4(),
            occurred_at=datetime.now(UTC),
            actor_kind=actor_kind,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            context=event_context,
        )
        await self.events.append(event)
        return event

    @staticmethod
    def _validate_actor(
        *, actor_kind: AuditActorKind, actor_user_id: UUID | None
    ) -> None:
        if not isinstance(actor_kind, AuditActorKind):
            raise ValueError("actor_kind is invalid")
        if actor_kind is AuditActorKind.AUTHENTICATED and not isinstance(
            actor_user_id, UUID
        ):
            raise ValueError("authenticated actor requires actor_user_id")
        if actor_kind is AuditActorKind.ANONYMOUS and actor_user_id is not None:
            raise ValueError("anonymous actor cannot have actor_user_id")

    @staticmethod
    def _validate_resource_id(resource_id: str) -> None:
        try:
            parsed_id = UUID(resource_id)
        except (TypeError, ValueError, AttributeError):
            raise ValueError("resource_id must be a UUID") from None
        if str(parsed_id) != resource_id:
            raise ValueError("resource_id must use canonical UUID format")

    @staticmethod
    def _validate_context_values(context: Mapping[str, str]) -> None:
        if any(not isinstance(value, str) for value in context.values()):
            raise ValueError("context values must be strings")

        method = context.get("http_method")
        if method is not None and method not in _ALLOWED_HTTP_METHODS:
            raise ValueError("context contains an invalid http_method")

        reason_code = context.get("reason_code")
        if reason_code is not None and reason_code not in _ALLOWED_REASON_CODES:
            raise ValueError("context contains an invalid reason_code")

        route_template = context.get("route_template")
        if route_template is not None and not _ROUTE_TEMPLATE_PATTERN.fullmatch(
            route_template
        ):
            raise ValueError("context contains an invalid route_template")
