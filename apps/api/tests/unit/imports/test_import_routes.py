"""Contrato HTTP da prévia de importação do acervo legado (#45)."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.imports.import_legacy_archive import (
    ImportLegacyArchiveUseCase,
)
from crm_api.application.imports.preview_legacy_import import (
    PreviewLegacyImportUseCase,
)
from crm_api.domain.audit.entities import AuditEvent
from crm_api.domain.auth.entities import User
from crm_api.domain.clients.entities import ClientFolder
from crm_api.domain.documents.entities import StoredContent, StoredDocument
from crm_api.infrastructure.documents.storage import PrivateFilesystemDocumentStorage
from crm_api.infrastructure.imports.scanner import FilesystemLegacyArchiveScanner
from crm_api.main import app
from crm_api.presentation.auth import dependencies as auth_dependencies
from crm_api.presentation.imports import dependencies as import_dependencies

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"

OWNER = User(
    id=UUID("00000000-0000-0000-0000-000000000045"),
    email="owner@deltaforce.internal",
    full_name="Owner Synthetic",
    password_hash="not-returned",
    is_active=True,
)


@dataclass
class _MemoryClientRepository:
    folders: list[ClientFolder] = field(default_factory=list)

    def add(self, display_name: str) -> None:
        self.folders.append(
            ClientFolder(
                id=uuid4(),
                display_name=display_name,
                profile_data={},
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

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

    async def get(self, *, id: UUID) -> StoredDocument | None:  # pragma: no cover
        return self.documents.get(id)

    async def checksum_exists(
        self, *, client_folder_id: UUID, checksum_sha256: str
    ) -> bool:
        return any(
            d.client_folder_id == client_folder_id
            and d.checksum_sha256 == checksum_sha256
            for d in self.documents.values()
        )


@dataclass
class _SpyTransaction:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:  # pragma: no cover
        return None


@dataclass
class _RecordingAuditRepository:
    events: list[AuditEvent] = field(default_factory=list)

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)

    async def list_recent(self, **_: object) -> list[AuditEvent]:  # pragma: no cover
        return []


@pytest.fixture
def harness() -> Iterator[tuple[TestClient, _MemoryClientRepository]]:
    repository = _MemoryClientRepository()

    app.dependency_overrides[auth_dependencies.get_current_user] = lambda: OWNER
    app.dependency_overrides[import_dependencies.get_preview_legacy_import_use_case] = (
        lambda: PreviewLegacyImportUseCase(
            clients=repository, scanner=FilesystemLegacyArchiveScanner()
        )
    )
    try:
        with TestClient(app) as client:
            yield client, repository
    finally:
        app.dependency_overrides.clear()


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def test_preview_reports_matches_and_gaps_without_writing(
    harness: tuple[TestClient, _MemoryClientRepository], tmp_path: Path
) -> None:
    client, repository = harness
    repository.add("Ana Souza")
    root = tmp_path / "acervo"
    _write(root / "Ana Souza" / "contrato.pdf", PDF_BYTES)
    _write(root / "Desconhecido" / "rg.pdf", PDF_BYTES)
    _write(root / "Ana Souza" / "planilha.xlsx", b"PK\x03\x04zip")

    response = client.post("/imports/legacy/preview", json={"source_path": str(root)})

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == {
        "matched": 1,
        "client_not_found": 1,
        "client_ambiguous": 0,
        "unsupported_format": 1,
        "unreadable": 0,
        "total": 3,
    }
    matched = next(
        item
        for item in body["items"]
        if item["relative_path"] == "Ana Souza/contrato.pdf"
    )
    assert matched["status"] == "matched"
    assert matched["media_type"] == "application/pdf"
    assert matched["matched_client_id"] == str(repository.folders[0].id)


def test_preview_rejects_a_missing_source_folder(
    harness: tuple[TestClient, _MemoryClientRepository], tmp_path: Path
) -> None:
    client, _ = harness

    response = client.post(
        "/imports/legacy/preview", json={"source_path": str(tmp_path / "nao-existe")}
    )

    assert response.status_code == 422


def test_preview_requires_a_source_path(
    harness: tuple[TestClient, _MemoryClientRepository],
) -> None:
    client, _ = harness

    response = client.post("/imports/legacy/preview", json={"source_path": ""})

    assert response.status_code == 422


def test_execute_imports_matched_files_and_reports(tmp_path: Path) -> None:
    repository = _MemoryClientRepository()
    repository.add("Ana Souza")
    documents = _MemoryDocumentRepository()
    storage = PrivateFilesystemDocumentStorage(root=tmp_path / "private")
    root = tmp_path / "acervo"
    _write(root / "Ana Souza" / "contrato.pdf", PDF_BYTES)
    _write(root / "Desconhecido" / "rg.pdf", PDF_BYTES)

    app.dependency_overrides[auth_dependencies.get_current_user] = lambda: OWNER
    app.dependency_overrides[import_dependencies.get_import_legacy_archive_use_case] = (
        lambda: ImportLegacyArchiveUseCase(
            clients=repository,
            documents=documents,
            storage=storage,
            scanner=FilesystemLegacyArchiveScanner(),
            audit=RecordAuditEventUseCase(events=_RecordingAuditRepository()),
            transaction=_SpyTransaction(),
        )
    )
    try:
        with TestClient(app) as client:
            response = client.post("/imports/legacy", json={"source_path": str(root)})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["imported"] == 1
    assert body["summary"]["skipped"] == 1
    imported = next(item for item in body["items"] if item["outcome"] == "imported")
    assert imported["relative_path"] == "Ana Souza/contrato.pdf"
    assert imported["document_id"] is not None
    assert len(documents.documents) == 1
