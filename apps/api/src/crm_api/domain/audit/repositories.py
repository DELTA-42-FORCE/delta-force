"""Portas de persistência usadas pela auditoria."""

from typing import Protocol

from crm_api.domain.audit.entities import AuditEvent, AuditEventCursor


class AuditEventRepository(Protocol):
    """Persiste e consulta eventos sem expor o adaptador concreto."""

    async def append(self, event: AuditEvent) -> None: ...

    async def list_recent(
        self, *, limit: int, before: AuditEventCursor | None
    ) -> list[AuditEvent]: ...
