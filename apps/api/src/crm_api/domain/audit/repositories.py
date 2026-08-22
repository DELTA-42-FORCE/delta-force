"""Portas de persistência usadas pela auditoria."""

from typing import Protocol

from crm_api.domain.audit.entities import (
    AuditAction,
    AuditEvent,
    AuditEventCursor,
    AuditResult,
)


class AuditEventRepository(Protocol):
    """Persiste e consulta eventos sem expor o adaptador concreto."""

    async def append(self, event: AuditEvent) -> None: ...

    async def list_recent(
        self,
        *,
        limit: int,
        before: AuditEventCursor | None,
        action: AuditAction | None,
        result: AuditResult | None,
    ) -> list[AuditEvent]: ...
