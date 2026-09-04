"""A execução copia, deduplica e audita a importação do acervo legado (#45)."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.imports.import_legacy_archive import (
    ImportLegacyArchiveUseCase,
)
from crm_api.domain.audit.entities import AuditEvent
from crm_api.domain.clients.entities import ClientFolder
from crm_api.domain.documents.entities import StoredContent, StoredDocument
from crm_api.domain.documents.errors import (
    DocumentStorageError,
    InsufficientStorageError,
)
from crm_api.domain.imports.entities import LegacyImportOutcome
from crm_api.infrastructure.documents.storage import (
    INCOMING_DIRECTORY_NAME,
    PrivateFilesystemDocumentStorage,
)
from crm_api.infrastructure.imports.scanner import FilesystemLegacyArchiveScanner

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x11" * 64 + b"\xff\xd9"
ACTOR_ID = UUID("00000000-0000-0000-0000-000000000045")


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _published(root: Path) -> list[Path]:
    incoming = root / INCOMING_DIRECTORY_NAME
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and incoming not in path.parents
    )


@dataclass
class _MemoryClientRepository:
    folders: list[ClientFolder] = field(default_factory=list)

    def add(self, display_name: str) -> ClientFolder:
        folder = ClientFolder(
            id=uuid4(),
            display_name=display_name,
            profile_data={},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.folders.append(folder)
        return folder

    async def find_by_display_name(self, *, display_name: str) -> list[ClientFolder]:
        target = display_name.strip().lower()
        return [f for f in self.folders if f.display_name.strip().lower() == target]


@dataclass
class _MemoryDocumentRepository:
    documents: dict[UUID, StoredDocument] = field(default_factory=dict)

    async def add(
        self,
        *,
        id: UUID,
        client_folder_id: UUID,
        original_filename: str,
        content: StoredContent,
    ) -> StoredDocument:
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
        self.documents[id] = document
        return document

    async def get(self, *, id: UUID) -> StoredDocument | None:
        return self.documents.get(id)

    async def checksum_exists(
        self, *, client_folder_id: UUID, checksum_sha256: str
    ) -> bool:
        return any(
            document.client_folder_id == client_folder_id
            and document.checksum_sha256 == checksum_sha256
            for document in self.documents.values()
        )


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

    async def rollback(self) -> None:
        self.rollback_calls += 1


@dataclass
class _StubStorage:
    """Storage que falha de forma controlada, para testar o mapeamento de erros."""

    error: Exception

    async def store(self, **_: object):
        raise self.error

    async def discard(self, **_: object) -> None:  # pragma: no cover - não usado
        return None


@dataclass
class _FirstStoreFails:
    """Falha uma vez para provar que o lote continua no arquivo seguinte."""

    delegate: PrivateFilesystemDocumentStorage
    calls: int = 0

    async def store(
        self,
        *,
        document_id: UUID,
        original_filename: str,
        chunks: AsyncIterator[bytes],
    ) -> StoredContent:
        self.calls += 1
        if self.calls == 1:
            raise DocumentStorageError("synthetic storage fault")
        return await self.delegate.store(
            document_id=document_id,
            original_filename=original_filename,
            chunks=chunks,
        )

    async def discard(self, *, storage_key: str) -> None:
        await self.delegate.discard(storage_key=storage_key)


def _use_case(
    *, clients: _MemoryClientRepository, storage, documents=None, audit=None, txn=None
):
    documents = documents or _MemoryDocumentRepository()
    audit_repo = audit or _RecordingAuditRepository()
    transaction = txn or _SpyTransaction()
    use_case = ImportLegacyArchiveUseCase(
        clients=clients,
        documents=documents,
        storage=storage,
        scanner=FilesystemLegacyArchiveScanner(),
        audit=RecordAuditEventUseCase(events=audit_repo),
        transaction=transaction,
    )
    return use_case, documents, audit_repo, transaction


async def test_imports_matched_files_deduplicates_and_audits(tmp_path: Path) -> None:
    root = tmp_path / "acervo"
    _write(root / "Ana Souza" / "contrato.pdf", PDF_BYTES)
    _write(root / "Ana Souza" / "copia.pdf", PDF_BYTES)  # mesmo conteúdo: duplicado
    _write(root / "Ana Souza" / "rg.jpg", JPEG_BYTES)
    _write(root / "Desconhecido" / "x.pdf", PDF_BYTES)
    _write(root / "Ana Souza" / "planilha.xlsx", b"PK\x03\x04zip")
    _write(root / "solto.pdf", PDF_BYTES)
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}

    clients = _MemoryClientRepository()
    clients.add("Ana Souza")
    storage = PrivateFilesystemDocumentStorage(root=tmp_path / "private")
    use_case, documents, audit, transaction = _use_case(
        clients=clients, storage=storage
    )

    result = await use_case.execute(actor_user_id=ACTOR_ID, source_path=str(root))

    assert result.summary == {
        "imported": 2,  # contrato.pdf e rg.jpg
        "duplicate": 1,  # copia.pdf
        "skipped": 2,  # Desconhecido/x.pdf e solto.pdf
        "unsupported_format": 1,  # planilha.xlsx
        "unreadable": 0,
        "insufficient_space": 0,
        "failed": 0,
        "total": 6,
    }
    # Só os dois importados viram documento e arquivo publicado.
    assert len(documents.documents) == 2
    assert len(_published(storage.root)) == 2
    assert sum(1 for e in audit.events if e.action == "document.stored") == 2
    assert transaction.commit_calls == 2
    # A origem permanece intacta.
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


async def test_insufficient_space_is_reported_without_importing(tmp_path: Path) -> None:
    root = tmp_path / "acervo"
    _write(root / "Ana Souza" / "contrato.pdf", PDF_BYTES)
    clients = _MemoryClientRepository()
    clients.add("Ana Souza")
    storage = _StubStorage(error=InsufficientStorageError("full"))
    use_case, documents, audit, transaction = _use_case(
        clients=clients, storage=storage
    )

    result = await use_case.execute(actor_user_id=ACTOR_ID, source_path=str(root))

    assert result.items[0].outcome is LegacyImportOutcome.INSUFFICIENT_SPACE
    assert documents.documents == {}
    assert audit.events == []
    assert transaction.commit_calls == 0


async def test_a_read_error_is_reported_as_unreadable(tmp_path: Path) -> None:
    root = tmp_path / "acervo"
    _write(root / "Ana Souza" / "contrato.pdf", PDF_BYTES)
    clients = _MemoryClientRepository()
    clients.add("Ana Souza")
    storage = _StubStorage(error=OSError("disk vanished"))
    use_case, _documents, _audit, _txn = _use_case(clients=clients, storage=storage)

    result = await use_case.execute(actor_user_id=ACTOR_ID, source_path=str(root))

    assert result.items[0].outcome is LegacyImportOutcome.UNREADABLE


async def test_an_unexpected_storage_failure_is_reported_and_does_not_stop_the_batch(
    tmp_path: Path,
) -> None:
    root = tmp_path / "acervo"
    _write(root / "Ana Souza" / "a.pdf", PDF_BYTES)
    _write(root / "Ana Souza" / "b.pdf", PDF_BYTES + b"\n")
    clients = _MemoryClientRepository()
    clients.add("Ana Souza")
    private_storage = PrivateFilesystemDocumentStorage(root=tmp_path / "private")
    storage = _FirstStoreFails(delegate=private_storage)
    use_case, documents, audit, transaction = _use_case(
        clients=clients, storage=storage
    )

    result = await use_case.execute(actor_user_id=ACTOR_ID, source_path=str(root))

    assert [item.outcome for item in result.items] == [
        LegacyImportOutcome.FAILED,
        LegacyImportOutcome.IMPORTED,
    ]
    assert len(documents.documents) == 1
    assert len(audit.events) == 1
    assert transaction.commit_calls == 1
