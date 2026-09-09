"""Importação com scanner, armazenamento e repositórios SQLite reais (#45)."""

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.imports.import_legacy_archive import ImportLegacyArchiveUseCase
from crm_api.infrastructure.audit.models import AuditEventModel
from crm_api.infrastructure.audit.repositories import SqlAlchemyAuditEventRepository
from crm_api.infrastructure.audit.transactions import SqlAlchemyTransaction
from crm_api.infrastructure.auth.models import UserModel
from crm_api.infrastructure.clients.models import ClientFolderModel
from crm_api.infrastructure.clients.repositories import SqlAlchemyClientFolderRepository
from crm_api.infrastructure.database import Base
from crm_api.infrastructure.documents.models import DocumentModel
from crm_api.infrastructure.documents.repositories import (
    SqlAlchemyDocumentMetadataRepository,
)
from crm_api.infrastructure.documents.storage import PrivateFilesystemDocumentStorage
from crm_api.infrastructure.imports.scanner import FilesystemLegacyArchiveScanner

pytestmark = pytest.mark.integration


async def test_import_persists_metadata_and_audit_then_deduplicates(
    tmp_path: Path,
) -> None:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{(tmp_path / 'import.sqlite3').as_posix()}"
    )
    source = tmp_path / "source"
    folder = source / "Cliente Sintetico"
    folder.mkdir(parents=True)
    content = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"
    original = folder / "documento.pdf"
    original.write_bytes(content)
    (folder / "invalido.txt").write_text("sintetico", encoding="utf-8")
    actor_id, client_id = uuid4(), uuid4()
    storage = PrivateFilesystemDocumentStorage(tmp_path / "private")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add(
                UserModel(
                    id=actor_id,
                    email="owner@example.invalid",
                    full_name="Sintetico",
                    password_hash="synthetic",
                )
            )
            session.add(
                ClientFolderModel(
                    id=client_id, display_name=folder.name, profile_data={}
                )
            )
            await session.commit()
            use_case = ImportLegacyArchiveUseCase(
                clients=SqlAlchemyClientFolderRepository(session),
                documents=SqlAlchemyDocumentMetadataRepository(session),
                storage=storage,
                scanner=FilesystemLegacyArchiveScanner(),
                audit=RecordAuditEventUseCase(SqlAlchemyAuditEventRepository(session)),
                transaction=SqlAlchemyTransaction(session),
            )
            first = await use_case.execute(
                actor_user_id=actor_id, source_path=str(source)
            )
            assert first.summary["imported"] == 1
            assert first.summary["unsupported_format"] == 1
            second = await use_case.execute(
                actor_user_id=actor_id, source_path=str(source)
            )
            assert second.summary["duplicate"] == 1
            assert second.summary["imported"] == 0
        async with factory() as session:
            document = (await session.scalars(select(DocumentModel))).one()
            assert document.client_folder_id == client_id
            assert (document.title, document.category, document.notes) == (
                None,
                None,
                None,
            )
            assert storage.resolve_path(document.storage_key).read_bytes() == content
            assert (
                await session.scalar(select(func.count()).select_from(DocumentModel))
                == 1
            )
            event = (await session.scalars(select(AuditEventModel))).one()
            assert event.action == "document.stored"
            assert event.actor_user_id == actor_id
            assert event.resource_id == str(document.id)
            assert event.context == {}
        assert original.read_bytes() == content
        assert len(list((tmp_path / "private").rglob("*.pdf"))) == 1
    finally:
        await engine.dispose()
