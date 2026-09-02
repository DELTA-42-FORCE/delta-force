from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Mapping
from uuid import UUID, uuid4

import pytest

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.documents.store_document import StoreDocumentUseCase
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditEvent,
    AuditEventCursor,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.clients.entities import ClientFolder
from crm_api.domain.clients.errors import ClientFolderNotFoundError
from crm_api.domain.documents.entities import (
    DocumentMediaType,
    StoredContent,
    StoredDocument,
)
from crm_api.domain.documents.errors import UnsupportedDocumentMediaTypeError

CHECKSUM = "a" * 64
STORAGE_KEY = "01/23/0123456789abcdef0123456789abcdef.pdf"


async def _stream() -> AsyncIterator[bytes]:
    yield b"%PDF-1.7 conteudo sintetico %%EOF"


@dataclass
class FakeAuditEventRepository:
    events: list[AuditEvent] = field(default_factory=list)

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)

    async def list_recent(
        self,
        *,
        limit: int,
        before: AuditEventCursor | None,
        action: AuditAction | None,
        result: AuditResult | None,
    ) -> list[AuditEvent]:
        del limit, before, action, result
        return []


@dataclass
class FakeTransaction:
    commit_calls: int = 0
    rollback_calls: int = 0

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


@dataclass
class FakeClientFolderRepository:
    existing: ClientFolder | None = None

    async def get(self, *, id: UUID) -> ClientFolder | None:
        if self.existing is not None and self.existing.id == id:
            return self.existing
        return None

    async def create(
        self, *, display_name: str, profile_data: Mapping[str, str]
    ) -> ClientFolder:
        raise AssertionError("storing a document must not create a client folder")


@dataclass
class FakeDocumentStorage:
    stored: list[tuple[UUID, str]] = field(default_factory=list)
    discarded: list[str] = field(default_factory=list)
    failure: Exception | None = None

    async def store(
        self,
        *,
        document_id: UUID,
        original_filename: str,
        chunks: AsyncIterator[bytes],
    ) -> StoredContent:
        async for _ in chunks:
            pass
        if self.failure is not None:
            raise self.failure
        self.stored.append((document_id, original_filename))
        return StoredContent(
            storage_key=STORAGE_KEY,
            media_type=DocumentMediaType.PDF,
            byte_size=33,
            checksum_sha256=CHECKSUM,
        )

    async def discard(self, *, storage_key: str) -> None:
        self.discarded.append(storage_key)


@dataclass
class FakeDocumentMetadataRepository:
    added: list[StoredDocument] = field(default_factory=list)
    failure: Exception | None = None

    async def add(
        self,
        *,
        id: UUID,
        client_folder_id: UUID,
        original_filename: str,
        content: StoredContent,
    ) -> StoredDocument:
        if self.failure is not None:
            raise self.failure
        document = StoredDocument(
            id=id,
            client_folder_id=client_folder_id,
            original_filename=original_filename,
            storage_key=content.storage_key,
            media_type=content.media_type,
            byte_size=content.byte_size,
            checksum_sha256=content.checksum_sha256,
            stored_at=datetime.now(UTC),
        )
        self.added.append(document)
        return document

    async def get(self, *, id: UUID) -> StoredDocument | None:
        return next((document for document in self.added if document.id == id), None)


@dataclass
class _Harness:
    use_case: StoreDocumentUseCase
    clients: FakeClientFolderRepository
    documents: FakeDocumentMetadataRepository
    storage: FakeDocumentStorage
    events: FakeAuditEventRepository
    transaction: FakeTransaction
    client_folder_id: UUID


def _build_harness(*, folder_exists: bool = True) -> _Harness:
    folder = ClientFolder(
        id=uuid4(),
        display_name="Cliente Sintético",
        profile_data={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    clients = FakeClientFolderRepository(existing=folder if folder_exists else None)
    documents = FakeDocumentMetadataRepository()
    storage = FakeDocumentStorage()
    events = FakeAuditEventRepository()
    transaction = FakeTransaction()
    return _Harness(
        use_case=StoreDocumentUseCase(
            clients=clients,
            documents=documents,
            storage=storage,
            audit=RecordAuditEventUseCase(events=events),
            transaction=transaction,
        ),
        clients=clients,
        documents=documents,
        storage=storage,
        events=events,
        transaction=transaction,
        client_folder_id=folder.id,
    )


async def test_stores_the_document_and_audits_the_authenticated_action() -> None:
    harness = _build_harness()
    actor_id = uuid4()

    document = await harness.use_case.execute(
        actor_user_id=actor_id,
        client_folder_id=harness.client_folder_id,
        original_filename="contrato.pdf",
        chunks=_stream(),
    )

    assert document.client_folder_id == harness.client_folder_id
    assert document.storage_key == STORAGE_KEY
    assert document.media_type is DocumentMediaType.PDF
    assert harness.storage.stored == [(document.id, "contrato.pdf")]
    assert harness.transaction.commit_calls == 1
    assert harness.storage.discarded == []

    event = harness.events.events[0]
    assert event.actor_user_id == actor_id
    assert event.action is AuditAction.DOCUMENT_STORED
    assert event.resource_type is AuditResourceType.DOCUMENT
    assert event.resource_id == str(document.id)
    assert event.result is AuditResult.SUCCESS


async def test_refuses_an_unknown_client_folder_before_writing_anything() -> None:
    harness = _build_harness(folder_exists=False)

    with pytest.raises(ClientFolderNotFoundError):
        await harness.use_case.execute(
            actor_user_id=uuid4(),
            client_folder_id=uuid4(),
            original_filename="contrato.pdf",
            chunks=_stream(),
        )

    assert harness.storage.stored == []
    assert harness.documents.added == []
    assert harness.events.events == []
    assert harness.transaction.commit_calls == 0


async def test_does_not_touch_the_database_when_the_content_is_rejected() -> None:
    harness = _build_harness()
    harness.storage.failure = UnsupportedDocumentMediaTypeError("not a pdf")

    with pytest.raises(UnsupportedDocumentMediaTypeError):
        await harness.use_case.execute(
            actor_user_id=uuid4(),
            client_folder_id=harness.client_folder_id,
            original_filename="contrato.pdf",
            chunks=_stream(),
        )

    assert harness.documents.added == []
    assert harness.events.events == []
    assert harness.transaction.commit_calls == 0
    assert harness.transaction.rollback_calls == 0


async def test_discards_the_published_file_when_the_metadata_cannot_persist() -> None:
    harness = _build_harness()
    harness.documents.failure = RuntimeError("metadata write failed")

    with pytest.raises(RuntimeError, match="metadata write failed"):
        await harness.use_case.execute(
            actor_user_id=uuid4(),
            client_folder_id=harness.client_folder_id,
            original_filename="contrato.pdf",
            chunks=_stream(),
        )

    assert harness.transaction.rollback_calls == 1
    assert harness.transaction.commit_calls == 0
    assert harness.storage.discarded == [STORAGE_KEY]
