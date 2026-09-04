"""Seleciona clientes por situação documental sem resolver endereços."""

from dataclasses import dataclass

from crm_api.domain.communications.entities import RecipientCandidate
from crm_api.domain.communications.repositories import CommunicationRepository
from crm_api.domain.documents.entities import DocumentStatus


@dataclass(frozen=True, slots=True)
class ListRecipientCandidatesUseCase:
    repository: CommunicationRepository

    async def execute(
        self, *, document_status: DocumentStatus, limit: int
    ) -> list[RecipientCandidate]:
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("recipient candidate limit must be between 1 and 100")
        if document_status is DocumentStatus.RECEIVED_REGULAR:
            raise ValueError("recipient candidates require a pending document status")
        return await self.repository.list_recipient_candidates(
            document_status=document_status, limit=limit
        )
