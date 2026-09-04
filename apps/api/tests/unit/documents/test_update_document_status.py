"""Regras da atualização auditada do status documental (#23)."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.documents.update_document_status import (
    UpdateDocumentStatusUseCase,
)
from crm_api.domain.audit.entities import AuditEvent
from crm_api.domain.documents.entities import (
    DocumentMediaType,
    DocumentStatus,
    StoredDocument,
)
from crm_api.domain.documents.errors import DocumentNotFoundError

ACTOR_ID = UUID("00000000-0000-0000-0000-000000000023")
FOLDER_ID = UUID("00000000-0000-0000-0000-0000000000f0")


def _document() -> StoredDocument:
    return StoredDocument(
        id=uuid4(),
        client_folder_id=FOLDER_ID,
        original_filename="documento.pdf",
        storage_key="aa/bb/documento.pdf",
        media_type=DocumentMediaType.PDF,
        byte_size=32,
        checksum_sha256="a" * 64,
        stored_at=datetime.now(UTC),
    )


@dataclass
class _DocumentRepository:
    document: StoredDocument
    failure: BaseException | None = None
    update_calls: int = 0

    async def get(self, *, id: UUID) -> StoredDocument | None:
        return self.document if id == self.document.id else None

    async def update_status(
        self, *, id: UUID, status: DocumentStatus
    ) -> StoredDocument | None:
        assert id == self.document.id
        self.update_calls += 1
        if self.failure is not None:
            raise self.failure
        self.document = replace(self.document, status=status)
        return self.document


@dataclass
class _AuditRepository:
    events: list[AuditEvent] = field(default_factory=list)

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)


@dataclass
class _Transaction:
    commits: int = 0
    rollbacks: int = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _harness() -> tuple[
    UpdateDocumentStatusUseCase,
    _DocumentRepository,
    _AuditRepository,
    _Transaction,
]:
    documents = _DocumentRepository(_document())
    events = _AuditRepository()
    transaction = _Transaction()
    return (
        UpdateDocumentStatusUseCase(
            documents=documents,  # type: ignore[arg-type]
            audit=RecordAuditEventUseCase(events=events),  # type: ignore[arg-type]
            transaction=transaction,
        ),
        documents,
        events,
        transaction,
    )


async def test_updates_status_and_records_old_and_new_values() -> None:
    use_case, documents, events, transaction = _harness()

    updated = await use_case.execute(
        actor_user_id=ACTOR_ID,
        client_folder_id=FOLDER_ID,
        document_id=documents.document.id,
        status=DocumentStatus.RECEIVED_REGULAR,
    )

    assert updated.status is DocumentStatus.RECEIVED_REGULAR
    assert transaction.commits == 1
    assert transaction.rollbacks == 0
    event = events.events[0]
    assert event.action == "document.status_updated"
    assert event.context == {
        "previous_status": "pending",
        "new_status": "received_regular",
    }


async def test_same_status_is_an_idempotent_no_op() -> None:
    use_case, documents, events, transaction = _harness()

    unchanged = await use_case.execute(
        actor_user_id=ACTOR_ID,
        client_folder_id=FOLDER_ID,
        document_id=documents.document.id,
        status=DocumentStatus.PENDING,
    )

    assert unchanged is documents.document
    assert documents.update_calls == 0
    assert events.events == []
    assert transaction.commits == 0


async def test_document_from_another_folder_is_hidden() -> None:
    use_case, documents, events, transaction = _harness()

    with pytest.raises(DocumentNotFoundError):
        await use_case.execute(
            actor_user_id=ACTOR_ID,
            client_folder_id=uuid4(),
            document_id=documents.document.id,
            status=DocumentStatus.INCORRECT_INCOMPLETE,
        )

    assert events.events == []
    assert transaction.commits == 0


async def test_repository_failure_rolls_the_transaction_back() -> None:
    use_case, documents, events, transaction = _harness()
    documents.failure = RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        await use_case.execute(
            actor_user_id=ACTOR_ID,
            client_folder_id=FOLDER_ID,
            document_id=documents.document.id,
            status=DocumentStatus.INCORRECT_INCOMPLETE,
        )

    assert events.events == []
    assert transaction.commits == 0
    assert transaction.rollbacks == 1
