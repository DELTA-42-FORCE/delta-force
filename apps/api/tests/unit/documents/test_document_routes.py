"""Contrato HTTP das rotas autenticadas de anexo, consulta e exportação (#22)."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.documents.export_client_document import (
    ExportClientDocumentUseCase,
)
from crm_api.application.documents.get_client_document import (
    GetClientDocumentUseCase,
)
from crm_api.application.documents.list_client_documents import (
    ListClientDocumentsUseCase,
)
from crm_api.application.documents.store_document import StoreDocumentUseCase
from crm_api.domain.audit.entities import AuditEvent
from crm_api.domain.auth.entities import User
from crm_api.domain.clients.entities import ClientFolder
from crm_api.domain.documents.entities import (
    DocumentCursor,
    StoredContent,
    StoredDocument,
)
from crm_api.infrastructure.documents.storage import PrivateFilesystemDocumentStorage
from crm_api.main import app
from crm_api.presentation.auth import dependencies as auth_dependencies
from crm_api.presentation.documents import dependencies as document_dependencies
from crm_api.presentation.documents.routes import router as documents_router

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x11" * 64 + b"\xff\xd9"

OWNER_ID = UUID("00000000-0000-0000-0000-000000000022")
OWNER = User(
    id=OWNER_ID,
    email="owner@deltaforce.internal",
    full_name="Owner Synthetic",
    password_hash="not-returned",
    is_active=True,
)


@dataclass
class MemoryClientFolderRepository:
    folders: dict[UUID, ClientFolder] = field(default_factory=dict)

    def add_folder(self) -> ClientFolder:
        folder = ClientFolder(
            id=uuid4(),
            display_name="Cliente Sintético",
            profile_data={},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.folders[folder.id] = folder
        return folder

    async def get(self, *, id: UUID) -> ClientFolder | None:
        return self.folders.get(id)

    async def create(
        self, *, display_name: str, profile_data: Mapping[str, str]
    ) -> ClientFolder:
        raise AssertionError("document routes must not create client folders")


@dataclass
class MemoryDocumentMetadataRepository:
    documents: dict[UUID, StoredDocument] = field(default_factory=dict)

    async def add(
        self,
        *,
        id: UUID,
        client_folder_id: UUID,
        original_filename: str,
        title: str | None,
        category: str | None,
        notes: str | None,
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
            title=title,
            category=category,
            notes=notes,
        )
        self.documents[id] = document
        return document

    async def get(self, *, id: UUID) -> StoredDocument | None:
        return self.documents.get(id)

    async def list_for_client(
        self,
        *,
        client_folder_id: UUID,
        limit: int,
        before: DocumentCursor | None,
    ) -> list[StoredDocument]:
        ordered = sorted(
            (
                document
                for document in self.documents.values()
                if document.client_folder_id == client_folder_id
            ),
            key=lambda document: (document.stored_at, document.id),
            reverse=True,
        )
        if before is not None:
            ordered = [
                document
                for document in ordered
                if (document.stored_at, document.id) < (before.stored_at, before.id)
            ]
        return ordered[:limit]


@dataclass
class SpyTransaction:
    commit_calls: int = 0
    rollback_calls: int = 0

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


@dataclass
class _Harness:
    client: TestClient
    folders: MemoryClientFolderRepository
    documents: MemoryDocumentMetadataRepository
    storage: PrivateFilesystemDocumentStorage
    events: list[AuditEvent]
    folder_id: UUID


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[_Harness]:
    folders = MemoryClientFolderRepository()
    documents = MemoryDocumentMetadataRepository()
    storage = PrivateFilesystemDocumentStorage(root=tmp_path / "documents")
    events: list[AuditEvent] = []
    transaction = SpyTransaction()

    @dataclass
    class RecordingAuditRepository:
        async def append(self, event: AuditEvent) -> None:
            events.append(event)

        async def list_recent(self, **_: object) -> list[AuditEvent]:
            return []

    audit = RecordAuditEventUseCase(events=RecordingAuditRepository())
    folder = folders.add_folder()

    app.dependency_overrides[auth_dependencies.get_current_user] = lambda: OWNER
    app.dependency_overrides[document_dependencies.get_store_document_use_case] = (
        lambda: StoreDocumentUseCase(
            clients=folders,
            documents=documents,
            storage=storage,
            audit=audit,
            transaction=transaction,
        )
    )
    app.dependency_overrides[
        document_dependencies.get_list_client_documents_use_case
    ] = lambda: ListClientDocumentsUseCase(
        clients=folders, documents=documents, audit=audit, transaction=transaction
    )
    app.dependency_overrides[document_dependencies.get_get_client_document_use_case] = (
        lambda: GetClientDocumentUseCase(
            documents=documents, audit=audit, transaction=transaction
        )
    )
    app.dependency_overrides[
        document_dependencies.get_export_client_document_use_case
    ] = lambda: ExportClientDocumentUseCase(
        documents=documents, storage=storage, audit=audit, transaction=transaction
    )

    try:
        with TestClient(app) as test_client:
            yield _Harness(
                client=test_client,
                folders=folders,
                documents=documents,
                storage=storage,
                events=events,
                folder_id=folder.id,
            )
    finally:
        app.dependency_overrides.clear()


def _attach(
    harness: _Harness,
    *,
    filename: str = "contrato.pdf",
    payload: bytes = PDF_BYTES,
    folder_id: UUID | None = None,
    data: dict[str, str] | None = None,
):
    return harness.client.post(
        f"/clients/{folder_id or harness.folder_id}/documents",
        files={"file": (filename, payload, "application/octet-stream")},
        data=data or {},
    )


def test_owner_attaches_a_pdf_to_a_client_folder(harness: _Harness) -> None:
    response = _attach(harness)

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "contrato.pdf"
    assert body["media_type"] == "application/pdf"
    assert body["byte_size"] == len(PDF_BYTES)
    assert (body["title"], body["category"], body["notes"]) == (None, None, None)
    # A chave interna do arquivo não pode vazar no contrato HTTP.
    assert "storage_key" not in body
    assert harness.events[-1].action == "document.stored"

    stored = harness.documents.documents[UUID(body["id"])]
    assert harness.storage.resolve_path(stored.storage_key).read_bytes() == PDF_BYTES


def test_owner_attaches_a_jpeg_with_optional_annotations(harness: _Harness) -> None:
    response = _attach(
        harness,
        filename="digitalizacao.jpeg",
        payload=JPEG_BYTES,
        data={
            "title": "  RG  frente ",
            "category": "identidade",
            "notes": " ver verso",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["media_type"] == "image/jpeg"
    assert body["title"] == "RG frente"
    assert body["category"] == "identidade"
    assert body["notes"] == "ver verso"


def test_attaching_an_unsupported_format_is_refused_with_a_clear_message(
    harness: _Harness,
) -> None:
    response = _attach(harness, payload=b"PK\x03\x04conteudo compactado")

    assert response.status_code == 415
    assert "PDF" in response.json()["detail"]
    assert harness.documents.documents == {}


def test_attaching_a_renamed_jpeg_as_pdf_is_refused(harness: _Harness) -> None:
    response = _attach(harness, filename="disfarcado.pdf", payload=JPEG_BYTES)

    assert response.status_code == 415
    assert "does not match" in response.json()["detail"]


def test_attaching_an_unsafe_name_is_refused(harness: _Harness) -> None:
    response = _attach(harness, filename="planilha.xlsx")

    assert response.status_code == 422
    assert harness.documents.documents == {}


def test_attaching_a_truncated_document_is_refused(harness: _Harness) -> None:
    response = _attach(harness, payload=PDF_BYTES.replace(b"%%EOF\n", b""))

    assert response.status_code == 415
    assert "truncated" in response.json()["detail"]


def test_attaching_to_an_unknown_client_folder_returns_not_found(
    harness: _Harness,
) -> None:
    response = _attach(harness, folder_id=uuid4())

    assert response.status_code == 404
    assert response.json()["detail"] == "client folder not found"


def test_owner_lists_the_documents_of_a_folder_and_the_query_is_audited(
    harness: _Harness,
) -> None:
    _attach(harness)
    _attach(harness, filename="rg.jpg", payload=JPEG_BYTES)

    response = harness.client.get(f"/clients/{harness.folder_id}/documents")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] is None
    assert harness.events[-1].action == "document.viewed"


def test_listing_paginates_by_a_stable_cursor(harness: _Harness) -> None:
    _attach(harness)
    _attach(harness, filename="rg.jpg", payload=JPEG_BYTES)

    first = harness.client.get(
        f"/clients/{harness.folder_id}/documents", params={"limit": 1}
    ).json()

    assert len(first["items"]) == 1
    assert first["next_cursor"] is not None

    second = harness.client.get(
        f"/clients/{harness.folder_id}/documents",
        params={
            "limit": 1,
            "before_stored_at": first["next_cursor"]["stored_at"],
            "before_id": first["next_cursor"]["id"],
        },
    ).json()

    assert len(second["items"]) == 1
    assert second["items"][0]["id"] != first["items"][0]["id"]


def test_owner_reads_the_metadata_of_one_document(harness: _Harness) -> None:
    document_id = _attach(harness).json()["id"]

    response = harness.client.get(
        f"/clients/{harness.folder_id}/documents/{document_id}"
    )

    assert response.status_code == 200
    assert response.json()["id"] == document_id
    assert harness.events[-1].action == "document.viewed"
    assert harness.events[-1].resource_id == document_id


def test_a_document_is_not_reachable_through_another_folder(
    harness: _Harness,
) -> None:
    document_id = _attach(harness).json()["id"]
    other_folder = harness.folders.add_folder()

    response = harness.client.get(f"/clients/{other_folder.id}/documents/{document_id}")

    # Mesma resposta de inexistente: não revela anexos de outro cliente.
    assert response.status_code == 404
    assert response.json()["detail"] == "document not found"


def test_owner_exports_an_authorized_copy_of_the_document(harness: _Harness) -> None:
    document_id = _attach(harness).json()["id"]

    response = harness.client.get(
        f"/clients/{harness.folder_id}/documents/{document_id}/content"
    )

    assert response.status_code == 200
    assert response.content == PDF_BYTES
    assert response.headers["content-type"].startswith("application/pdf")
    # Cópia é sempre download, nunca renderização inline.
    assert response.headers["content-disposition"].startswith("attachment;")
    assert "contrato.pdf" in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert harness.events[-1].action == "document.exported"
    assert harness.events[-1].result == "success"


def test_export_reports_a_missing_file_and_audits_the_failure(
    harness: _Harness,
) -> None:
    body = _attach(harness).json()
    stored = harness.documents.documents[UUID(body["id"])]
    harness.storage.resolve_path(stored.storage_key).unlink()

    response = harness.client.get(
        f"/clients/{harness.folder_id}/documents/{body['id']}/content"
    )

    assert response.status_code == 500
    assert "não pôde ser lido" in response.json()["detail"]
    assert harness.events[-1].action == "document.exported"
    assert harness.events[-1].result == "failure"
    assert harness.events[-1].context["reason_code"] == "document_content_unavailable"


def test_every_document_route_requires_the_authenticated_owner() -> None:
    """A sessão é exigida no servidor; o 401 real é coberto na integração."""
    routes = list(documents_router.routes)

    assert len(routes) == 4
    for route in routes:
        dependants = route.dependant.dependencies  # type: ignore[attr-defined]
        dependency_names = {
            dependant.call.__name__
            for dependant in dependants
            if dependant.call is not None
        }
        assert "get_current_user" in dependency_names
