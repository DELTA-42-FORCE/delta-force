"""Persistência SQLite dos modelos e seleção por status documental."""

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.communications.templates import CreateMessageTemplateUseCase
from crm_api.domain.documents.entities import DocumentStatus
from crm_api.infrastructure.audit.models import AuditEventModel
from crm_api.infrastructure.audit.repositories import SqlAlchemyAuditEventRepository
from crm_api.infrastructure.audit.transactions import SqlAlchemyTransaction
from crm_api.infrastructure.auth.models import UserModel
from crm_api.infrastructure.clients.models import ClientFolderModel
from crm_api.infrastructure.communications.models import MessageTemplateModel
from crm_api.infrastructure.communications.repositories import (
    SqlAlchemyCommunicationRepository,
)
from crm_api.infrastructure.database import get_engine, get_session_factory
from crm_api.infrastructure.documents.models import DocumentModel

pytestmark = pytest.mark.integration

_CLIENT_PREFIX = "Candidato comunicação "
_OWNER_DOMAIN = "@communications.deltaforce.internal"


def _requires_disposable_sqlite() -> None:
    engine = get_engine()
    if engine.dialect.name != "sqlite":
        pytest.skip("requires a sqlite+aiosqlite DATABASE_URL")
    database_path = Path(engine.url.database or "")
    if not database_path.stem.startswith("delta_force_integration_"):
        raise RuntimeError(
            "refusing communication test on non-disposable SQLite database"
        )


@pytest.fixture(autouse=True)
async def clear_communication_rows() -> AsyncIterator[None]:
    yield
    engine = get_engine()
    if engine.dialect.name != "sqlite":
        return
    async with get_session_factory()() as session:
        client_ids = select(ClientFolderModel.id).where(
            ClientFolderModel.display_name.like(f"{_CLIENT_PREFIX}%")
        )
        await session.execute(
            delete(AuditEventModel).where(
                AuditEventModel.resource_type == "message_template"
            )
        )
        await session.execute(delete(MessageTemplateModel))
        await session.execute(
            delete(DocumentModel).where(DocumentModel.client_folder_id.in_(client_ids))
        )
        await session.execute(
            delete(ClientFolderModel).where(
                ClientFolderModel.display_name.like(f"{_CLIENT_PREFIX}%")
            )
        )
        await session.execute(
            delete(UserModel).where(UserModel.email.like(f"%{_OWNER_DOMAIN}"))
        )
        await session.commit()


async def test_template_persists_and_records_sanitized_audit_event() -> None:
    _requires_disposable_sqlite()
    owner_id = uuid4()
    async with get_session_factory()() as session:
        session.add(
            UserModel(
                id=owner_id,
                email=f"owner-{owner_id}{_OWNER_DOMAIN}",
                full_name="Proprietário Sintético",
                password_hash="synthetic-password-hash",
                is_active=True,
            )
        )
        await session.flush()
        created = await CreateMessageTemplateUseCase(
            repository=SqlAlchemyCommunicationRepository(session),
            audit=RecordAuditEventUseCase(SqlAlchemyAuditEventRepository(session)),
            transaction=SqlAlchemyTransaction(session),
        ).execute(
            actor_user_id=owner_id,
            name="Pendência documental",
            subject="Documentação pendente",
            body="Conteúdo sintético não deve aparecer na auditoria.",
        )

    async with get_session_factory()() as session:
        stored = await session.get(MessageTemplateModel, created.id)
        event = await session.scalar(
            select(AuditEventModel).where(
                AuditEventModel.resource_id == str(created.id)
            )
        )

    assert stored is not None
    assert stored.name == "Pendência documental"
    assert event is not None
    assert event.action == "message_template.created"
    assert event.context == {}
    assert "Conteúdo sintético" not in repr(event.context)


async def test_recipient_candidates_are_grouped_by_client_and_status() -> None:
    _requires_disposable_sqlite()
    pending_client_id = uuid4()
    regular_client_id = uuid4()
    async with get_session_factory()() as session:
        session.add_all(
            [
                ClientFolderModel(
                    id=pending_client_id,
                    display_name=f"{_CLIENT_PREFIX}Pendente",
                    profile_data={"email": "not-returned@example.invalid"},
                ),
                ClientFolderModel(
                    id=regular_client_id,
                    display_name=f"{_CLIENT_PREFIX}Regular",
                    profile_data={},
                ),
            ]
        )
        await session.flush()
        for suffix in ("one", "two"):
            session.add(
                DocumentModel(
                    id=uuid4(),
                    client_folder_id=pending_client_id,
                    original_filename=f"{suffix}.pdf",
                    storage_key=f"communications/{uuid4()}.pdf",
                    media_type="application/pdf",
                    byte_size=20,
                    checksum_sha256=suffix[0] * 64,
                    status=DocumentStatus.PENDING.value,
                )
            )
        session.add(
            DocumentModel(
                id=uuid4(),
                client_folder_id=regular_client_id,
                original_filename="regular.pdf",
                storage_key=f"communications/{uuid4()}.pdf",
                media_type="application/pdf",
                byte_size=20,
                checksum_sha256="r" * 64,
                status=DocumentStatus.RECEIVED_REGULAR.value,
            )
        )
        await session.commit()

    async with get_session_factory()() as session:
        candidates = await SqlAlchemyCommunicationRepository(
            session
        ).list_recipient_candidates(
            document_status=DocumentStatus.PENDING,
            limit=100,
        )

    assert len(candidates) == 1
    assert candidates[0].client_id == pending_client_id
    assert candidates[0].matching_documents == 2
    assert not hasattr(candidates[0], "email")
