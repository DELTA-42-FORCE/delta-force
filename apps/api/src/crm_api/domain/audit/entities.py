"""Entidades imutáveis da trilha de auditoria."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping
from uuid import UUID


class AuditActorKind(StrEnum):
    """Origem identificada, ou não, de uma ação auditada."""

    AUTHENTICATED = "authenticated"
    ANONYMOUS = "anonymous"


class AuditResult(StrEnum):
    """Resultado observado para uma ação auditada."""

    SUCCESS = "success"
    DENIED = "denied"
    FAILURE = "failure"


class AuditAction(StrEnum):
    """Catálogo fechado das ações já implementadas no produto."""

    OWNER_SETUP = "auth.owner_setup"
    LOGIN = "auth.login"
    OWNER_PROFILE_VIEW = "auth.owner_profile_view"
    LOGOUT = "auth.logout"
    ACCESS_DENIED = "auth.access_denied"
    AUDIT_LOG_VIEW = "audit.log_view"


class AuditResourceType(StrEnum):
    """Catálogo fechado dos recursos auditáveis já implementados."""

    OWNER_ACCOUNT = "owner_account"
    SESSION = "session"
    ROUTE = "route"
    AUDIT_LOG = "audit_log"


@dataclass(frozen=True, slots=True)
class AuditEventCursor:
    """Posição exclusiva e estável na ordenação cronológica do log."""

    occurred_at: datetime
    id: UUID

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("audit cursor timestamp must include a timezone")
        if not isinstance(self.id, UUID):
            raise ValueError("audit cursor id must be a UUID")


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Registro imutável de uma ação relevante para segurança e LGPD."""

    id: UUID
    occurred_at: datetime
    actor_kind: AuditActorKind
    actor_user_id: UUID | None
    action: AuditAction
    resource_type: AuditResourceType
    resource_id: str | None
    result: AuditResult
    context: Mapping[str, str]

    def __post_init__(self) -> None:
        """Copia e congela o contexto recebido pelo evento."""
        object.__setattr__(self, "context", MappingProxyType(dict(self.context)))
