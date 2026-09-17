"""Auditoria da exportação: sucesso só ao fim do fluxo, falha no meio (#22)."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
from uuid import UUID, uuid4

import pytest

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.documents.export_client_document import (
    ExportClientDocumentUseCase,
)
from crm_api.domain.audit.entities import AuditEvent, AuditResult
from crm_api.domain.documents.entities import DocumentMediaType, StoredDocument
from crm_api.domain.documents.errors import DocumentContentUnavailableError

ACTOR_ID = UUID("00000000-0000-0000-0000-000000000022")
FOLDER_ID = UUID("00000000-0000-0000-0000-0000000000f0")
STORAGE_KEY = "01/23/0123456789abcdef0123456789abcdef.pdf"


def _document(payload: bytes = b"first-second") -> StoredDocument:
    return StoredDocument(
        id=uuid4(),
        client_folder_id=FOLDER_ID,
        original_filename="contrato.pdf",
        storage_key=STORAGE_KEY,
        media_type=DocumentMediaType.PDF,
        byte_size=len(payload),
        checksum_sha256=hashlib.sha256(payload).hexdigest(),
        stored_at=datetime.now(UTC),
    )


@dataclass
class _MetadataRepository:
    document: StoredDocument

    async def get(self, *, id: UUID) -> StoredDocument | None:
        return self.document if id == self.document.id else None

    async def add(self, **_: object) -> StoredDocument:  # pragma: no cover - unused
        raise AssertionError("export must not create documents")

    async def list_for_client(self, **_: object) -> list[StoredDocument]:
        raise AssertionError("export must not list documents")  # pragma: no cover


@dataclass
class _RecordingAuditRepository:
    events: list[AuditEvent] = field(default_factory=list)

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)

    async def list_recent(self, **_: object) -> list[AuditEvent]:  # pragma: no cover
        return []


@dataclass
class _SpyTransaction:
    commit_calls: int = 0
    rollback_calls: int = 0

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:  # pragma: no cover - unused here
        self.rollback_calls += 1


@dataclass
class _StubStorage:
    """Devolve blocos controlados e pode falhar num ponto escolhido do fluxo."""

    chunks: list[bytes]
    fail_before_index: int | None = None
    open_calls: int = 0

    async def _iter(self) -> AsyncIterator[bytes]:
        for index, chunk in enumerate(self.chunks):
            if index == self.fail_before_index:
                raise DocumentContentUnavailableError("read failed mid-stream")
            yield chunk

    def open_stream(self, *, storage_key: str) -> AsyncIterator[bytes]:
        assert storage_key == STORAGE_KEY
        self.open_calls += 1
        # `fail_before_index == 0` simula um arquivo que nem abre para leitura.
        if self.fail_before_index == 0:

            async def _fails() -> AsyncIterator[bytes]:
                raise DocumentContentUnavailableError("could not be opened")
                yield b""  # pragma: no cover - torna a função um gerador

            return _fails()
        return self._iter()

    async def store(self, **_: object):  # pragma: no cover - unused
        raise AssertionError("export must not store documents")

    async def discard(self, **_: object) -> None:  # pragma: no cover - unused
        raise AssertionError("export must not discard documents")


def _use_case(
    storage: _StubStorage, *, expected_payload: bytes | None = None
) -> tuple[ExportClientDocumentUseCase, _RecordingAuditRepository, _SpyTransaction]:
    document = _document(
        b"".join(storage.chunks) if expected_payload is None else expected_payload
    )
    audit_repository = _RecordingAuditRepository()
    transaction = _SpyTransaction()
    use_case = ExportClientDocumentUseCase(
        documents=_MetadataRepository(document),
        storage=storage,  # type: ignore[arg-type]
        audit=RecordAuditEventUseCase(events=audit_repository),
        transaction=transaction,
    )
    return use_case, audit_repository, transaction


async def _run(use_case: ExportClientDocumentUseCase, document_id: UUID):
    return await use_case.execute(
        actor_user_id=ACTOR_ID,
        client_folder_id=FOLDER_ID,
        document_id=document_id,
    )


async def test_success_is_audited_only_after_the_whole_stream_is_consumed() -> None:
    storage = _StubStorage(chunks=[b"first-", b"second"])
    use_case, audit, transaction = _use_case(storage)
    document = use_case.documents.document  # type: ignore[attr-defined]

    export = await _run(use_case, document.id)

    # A validação prévia não deve auditar sucesso antes do envio completo.
    assert audit.events == []
    assert transaction.commit_calls == 0

    collected = b""
    async for chunk in export.chunks:
        collected += chunk

    assert collected == b"first-second"
    assert len(audit.events) == 1
    assert audit.events[-1].action == "document.exported"
    assert audit.events[-1].result is AuditResult.SUCCESS
    assert transaction.commit_calls == 1


async def test_a_read_failure_before_response_is_audited_as_failure() -> None:
    storage = _StubStorage(chunks=[b"first-", b"second"], fail_before_index=1)
    use_case, audit, transaction = _use_case(storage)
    document = use_case.documents.document  # type: ignore[attr-defined]

    with pytest.raises(DocumentContentUnavailableError):
        await _run(use_case, document.id)

    assert len(audit.events) == 1
    assert audit.events[-1].result is AuditResult.FAILURE
    assert audit.events[-1].context["reason_code"] == "document_content_unavailable"
    assert transaction.commit_calls == 1


async def test_a_file_that_cannot_be_opened_is_audited_as_failure() -> None:
    storage = _StubStorage(chunks=[b"unused"], fail_before_index=0)
    use_case, audit, transaction = _use_case(storage)
    document = use_case.documents.document  # type: ignore[attr-defined]

    with pytest.raises(DocumentContentUnavailableError):
        await _run(use_case, document.id)

    assert len(audit.events) == 1
    assert audit.events[-1].result is AuditResult.FAILURE
    assert audit.events[-1].context["reason_code"] == "document_content_unavailable"
    assert transaction.commit_calls == 1


async def test_tampered_content_is_rejected_and_audited_as_failure() -> None:
    storage = _StubStorage(chunks=[b"altered-content"])
    use_case, audit, transaction = _use_case(
        storage, expected_payload=b"original-content"
    )
    document = use_case.documents.document  # type: ignore[attr-defined]

    with pytest.raises(DocumentContentUnavailableError):
        await _run(use_case, document.id)

    assert len(audit.events) == 1
    assert audit.events[-1].result is AuditResult.FAILURE
    assert audit.events[-1].context["reason_code"] == "document_integrity_mismatch"
    assert transaction.commit_calls == 1
