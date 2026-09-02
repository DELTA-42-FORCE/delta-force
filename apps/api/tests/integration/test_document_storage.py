from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.documents.store_document import StoreDocumentUseCase
from crm_api.domain.audit.entities import AuditAction, AuditResourceType
from crm_api.domain.documents.entities import DocumentMediaType, StoredContent
from crm_api.domain.documents.errors import UnsupportedDocumentMediaTypeError
from crm_api.infrastructure.audit.models import AuditEventModel
from crm_api.infrastructure.audit.repositories import SqlAlchemyAuditEventRepository
from crm_api.infrastructure.audit.transactions import SqlAlchemyTransaction
from crm_api.infrastructure.auth.models import UserModel
from crm_api.infrastructure.clients.models import ClientFolderModel
from crm_api.infrastructure.clients.repositories import SqlAlchemyClientFolderRepository
from crm_api.infrastructure.database import get_engine, get_session_factory
from crm_api.infrastructure.documents.models import DocumentModel
from crm_api.infrastructure.documents.repositories import (
    SqlAlchemyDocumentMetadataRepository,
)
from crm_api.infrastructure.documents.storage import PrivateFilesystemDocumentStorage

pytestmark = pytest.mark.integration

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"

CHECKSUM = "b" * 64


def _is_disposable_sqlite() -> bool:
    engine = get_engine()
    if engine.dialect.name != "sqlite":
        return False
    database_path = Path(engine.url.database or "")
    return database_path.stem.startswith("delta_force_integration_")


def _requires_disposable_sqlite() -> None:
    engine = get_engine()
    if engine.dialect.name != "sqlite":
        pytest.skip("requires a sqlite+aiosqlite DATABASE_URL")
    if not _is_disposable_sqlite():
        raise RuntimeError("refusing document test on non-disposable SQLite database")


@pytest.fixture(autouse=True)
async def clear_document_rows() -> AsyncIterator[None]:
    """Libera o banco compartilhado para os round-trips de migration da suíte."""
    yield
    if not _is_disposable_sqlite():
        return
    async with get_session_factory()() as session:
        await session.execute(delete(DocumentModel))
        await session.execute(
            delete(AuditEventModel).where(
                AuditEventModel.action == AuditAction.DOCUMENT_STORED.value
            )
        )
        await session.commit()


async def _stream(payload: bytes) -> AsyncIterator[bytes]:
    for start in range(0, len(payload), 16):
        end = start + 16
        yield payload[start:end]


def _synthetic_content(storage_key: str) -> StoredContent:
    return StoredContent(
        storage_key=storage_key,
        media_type=DocumentMediaType.PDF,
        byte_size=len(PDF_BYTES),
        checksum_sha256=CHECKSUM,
    )


async def _create_client_folder() -> ClientFolderModel:
    async with get_session_factory()() as session:
        folder = ClientFolderModel(
            display_name=f"Cliente Sintético {uuid4().hex[:8]}", profile_data={}
        )
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
    return folder


async def test_document_metadata_persists_without_the_binary() -> None:
    _requires_disposable_sqlite()
    folder = await _create_client_folder()
    document_id = uuid4()
    storage_key = f"{document_id.hex[:2]}/{document_id.hex[2:4]}/{document_id.hex}.pdf"

    async with get_session_factory()() as session:
        await SqlAlchemyDocumentMetadataRepository(session).add(
            id=document_id,
            client_folder_id=folder.id,
            original_filename="contrato assinado.pdf",
            content=_synthetic_content(storage_key),
        )
        await session.commit()

    async with get_session_factory()() as session:
        stored = await session.scalar(
            select(DocumentModel).where(DocumentModel.id == document_id)
        )

    assert stored is not None
    assert stored.client_folder_id == folder.id
    assert stored.storage_key == storage_key
    assert stored.media_type == "application/pdf"
    assert stored.byte_size == len(PDF_BYTES)
    assert stored.checksum_sha256 == CHECKSUM
    # O conteúdo não pertence ao banco: apenas a chave que o localiza.
    assert not hasattr(stored, "content")


async def test_document_requires_an_existing_client_folder() -> None:
    _requires_disposable_sqlite()
    document_id = uuid4()

    async with get_session_factory()() as session:
        session.add(
            DocumentModel(
                id=document_id,
                client_folder_id=uuid4(),
                original_filename="orfao.pdf",
                storage_key=f"aa/bb/{document_id.hex}.pdf",
                media_type="application/pdf",
                byte_size=10,
                checksum_sha256=CHECKSUM,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_document_rejects_an_unsupported_media_type() -> None:
    _requires_disposable_sqlite()
    folder = await _create_client_folder()
    document_id = uuid4()

    async with get_session_factory()() as session:
        session.add(
            DocumentModel(
                id=document_id,
                client_folder_id=folder.id,
                original_filename="planilha.xlsx",
                storage_key=f"cc/dd/{document_id.hex}.pdf",
                media_type="application/vnd.ms-excel",
                byte_size=10,
                checksum_sha256=CHECKSUM,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_document_storage_key_is_unique() -> None:
    _requires_disposable_sqlite()
    folder = await _create_client_folder()
    shared_key = f"ee/ff/{uuid4().hex}.pdf"

    async with get_session_factory()() as session:
        repository = SqlAlchemyDocumentMetadataRepository(session)
        await repository.add(
            id=uuid4(),
            client_folder_id=folder.id,
            original_filename="primeiro.pdf",
            content=_synthetic_content(shared_key),
        )
        await session.commit()

    async with get_session_factory()() as session:
        session.add(
            DocumentModel(
                id=uuid4(),
                client_folder_id=folder.id,
                original_filename="segundo.pdf",
                storage_key=shared_key,
                media_type="application/pdf",
                byte_size=10,
                checksum_sha256=CHECKSUM,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_storing_a_document_publishes_the_file_and_the_audit_event(
    tmp_path: Path,
) -> None:
    _requires_disposable_sqlite()
    folder = await _create_client_folder()
    owner_id = uuid4()
    storage = PrivateFilesystemDocumentStorage(root=tmp_path / "documents")

    async with get_session_factory()() as session:
        session.add(
            UserModel(
                id=owner_id,
                email=f"owner-{owner_id}@deltaforce.internal",
                full_name="Proprietário Sintético",
                password_hash="synthetic-password-hash",
                is_active=True,
            )
        )
        await session.flush()
        use_case = StoreDocumentUseCase(
            clients=SqlAlchemyClientFolderRepository(session),
            documents=SqlAlchemyDocumentMetadataRepository(session),
            storage=storage,
            audit=RecordAuditEventUseCase(
                events=SqlAlchemyAuditEventRepository(session)
            ),
            transaction=SqlAlchemyTransaction(session),
        )

        document = await use_case.execute(
            actor_user_id=owner_id,
            client_folder_id=folder.id,
            original_filename="contrato assinado.pdf",
            chunks=_stream(PDF_BYTES),
        )

    assert storage.resolve_path(document.storage_key).read_bytes() == PDF_BYTES

    async with get_session_factory()() as session:
        stored = await session.scalar(
            select(DocumentModel).where(DocumentModel.id == document.id)
        )
        event = await session.scalar(
            select(AuditEventModel).where(
                AuditEventModel.resource_id == str(document.id)
            )
        )

    assert stored is not None
    assert stored.media_type == "application/pdf"
    assert event is not None
    assert event.action == AuditAction.DOCUMENT_STORED.value
    assert event.resource_type == AuditResourceType.DOCUMENT.value
    assert event.actor_user_id == owner_id


async def test_rejected_content_leaves_no_file_and_no_metadata(
    tmp_path: Path,
) -> None:
    _requires_disposable_sqlite()
    folder = await _create_client_folder()
    owner_id = uuid4()
    storage = PrivateFilesystemDocumentStorage(root=tmp_path / "documents")

    async with get_session_factory()() as session:
        session.add(
            UserModel(
                id=owner_id,
                email=f"owner-{owner_id}@deltaforce.internal",
                full_name="Proprietário Sintético",
                password_hash="synthetic-password-hash",
                is_active=True,
            )
        )
        await session.flush()
        use_case = StoreDocumentUseCase(
            clients=SqlAlchemyClientFolderRepository(session),
            documents=SqlAlchemyDocumentMetadataRepository(session),
            storage=storage,
            audit=RecordAuditEventUseCase(
                events=SqlAlchemyAuditEventRepository(session)
            ),
            transaction=SqlAlchemyTransaction(session),
        )

        with pytest.raises(UnsupportedDocumentMediaTypeError):
            await use_case.execute(
                actor_user_id=owner_id,
                client_folder_id=folder.id,
                original_filename="planilha.pdf",
                chunks=_stream(b"PK\x03\x04conteudo compactado"),
            )
        await session.rollback()

    published = [path for path in storage.root.rglob("*") if path.is_file()]
    assert published == []

    async with get_session_factory()() as session:
        documents = (
            await session.scalars(
                select(DocumentModel).where(DocumentModel.client_folder_id == folder.id)
            )
        ).all()

    assert documents == []
