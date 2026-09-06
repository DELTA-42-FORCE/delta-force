"""Seleciona clientes por situação documental sem resolver endereços."""

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
from crm_api.domain.communications.entities import (
    RecipientCandidate,
    RecipientCandidateCursor,
)
from crm_api.domain.communications.repositories import CommunicationRepository
from crm_api.domain.documents.entities import DocumentStatus


@dataclass(frozen=True, slots=True)
class RecipientCandidatePage:
    items: tuple[RecipientCandidate, ...]
    next_cursor: RecipientCandidateCursor | None


@dataclass(frozen=True, slots=True)
class ListRecipientCandidatesUseCase:
    repository: CommunicationRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        document_status: DocumentStatus,
        limit: int,
        before: RecipientCandidateCursor | None,
    ) -> RecipientCandidatePage:
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("recipient candidate limit must be between 1 and 100")
        if document_status is DocumentStatus.RECEIVED_REGULAR:
            raise ValueError("recipient candidates require a pending document status")

        try:
            candidates = await self.repository.list_recipient_candidates(
                document_status=document_status,
                limit=limit + 1,
                before=before,
            )
            page_items = tuple(candidates[:limit])
            next_cursor = (
                RecipientCandidateCursor(
                    display_name=page_items[-1].display_name,
                    client_id=page_items[-1].client_id,
                )
                if len(candidates) > limit and page_items
                else None
            )
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.RECIPIENT_CANDIDATES_VIEWED,
                resource_type=AuditResourceType.CLIENT_FOLDER,
                resource_id=None,
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise

        return RecipientCandidatePage(items=page_items, next_cursor=next_cursor)
