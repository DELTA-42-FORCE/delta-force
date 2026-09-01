"""Caso de uso para buscar e listar pastas de clientes."""

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
from crm_api.domain.clients.entities import ClientFolder, ClientFolderCursor
from crm_api.domain.clients.repositories import ClientFolderRepository


@dataclass(frozen=True, slots=True)
class ClientFolderPage:
    items: tuple[ClientFolder, ...]
    next_cursor: ClientFolderCursor | None


@dataclass(frozen=True, slots=True)
class ListClientFoldersUseCase:
    """Consulta uma página estável do diretório e audita a visualização."""

    clients: ClientFolderRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        limit: int,
        before: ClientFolderCursor | None,
        query: str | None = None,
    ) -> ClientFolderPage:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")

        try:
            clients = await self.clients.search(
                query=query,
                limit=limit + 1,
                before=before,
            )
            page_items = tuple(clients[:limit])
            next_cursor = (
                ClientFolderCursor(
                    display_name=page_items[-1].display_name,
                    id=page_items[-1].id,
                )
                if len(clients) > limit and page_items
                else None
            )
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.CLIENT_FOLDER_VIEWED,
                resource_type=AuditResourceType.CLIENT_FOLDER,
                resource_id=None,
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise

        return ClientFolderPage(items=page_items, next_cursor=next_cursor)
