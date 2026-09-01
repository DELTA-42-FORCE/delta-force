from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.clients.create_client_folder import CreateClientFolderUseCase
from crm_api.domain.clients.entities import ClientFolderCursor
from crm_api.infrastructure.audit.models import AuditEventModel
from crm_api.infrastructure.audit.repositories import SqlAlchemyAuditEventRepository
from crm_api.infrastructure.audit.transactions import SqlAlchemyTransaction
from crm_api.infrastructure.clients.models import ClientFolderModel
from crm_api.infrastructure.clients.repositories import SqlAlchemyClientFolderRepository
from crm_api.infrastructure.auth.models import UserModel
from crm_api.infrastructure.database import get_engine, get_session_factory

pytestmark = pytest.mark.integration


def _requires_disposable_sqlite() -> None:
    engine = get_engine()
    if engine.dialect.name != "sqlite":
        pytest.skip("requires a sqlite+aiosqlite DATABASE_URL")
    database_path = Path(engine.url.database or "")
    if not database_path.stem.startswith("delta_force_integration_"):
        raise RuntimeError("refusing client test on non-disposable SQLite database")


async def test_client_folder_persists_name_and_optional_profile_data() -> None:
    _requires_disposable_sqlite()
    async with get_session_factory()() as session:
        created = await SqlAlchemyClientFolderRepository(session).create(
            display_name="Cliente de Persistência",
            profile_data={"observação": "documento pendente"},
        )
        await session.commit()

    async with get_session_factory()() as session:
        stored = await session.scalar(
            select(ClientFolderModel).where(ClientFolderModel.id == created.id)
        )

    assert stored is not None
    assert stored.display_name == "Cliente de Persistência"
    assert stored.profile_data == {"observação": "documento pendente"}


async def test_client_folder_database_rejects_blank_identifying_name() -> None:
    _requires_disposable_sqlite()
    async with get_session_factory()() as session:
        session.add(ClientFolderModel(display_name="  ", profile_data={}))
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_create_client_folder_records_authenticated_audit_event() -> None:
    _requires_disposable_sqlite()
    owner_id = uuid4()
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
        use_case = CreateClientFolderUseCase(
            clients=SqlAlchemyClientFolderRepository(session),
            audit=RecordAuditEventUseCase(
                events=SqlAlchemyAuditEventRepository(session)
            ),
            transaction=SqlAlchemyTransaction(session),
        )

        created = await use_case.execute(
            actor_user_id=owner_id,
            display_name="Cliente Auditado",
        )

    async with get_session_factory()() as session:
        event = await session.scalar(
            select(AuditEventModel).where(
                AuditEventModel.resource_id == str(created.id)
            )
        )

    assert event is not None
    assert event.actor_user_id == owner_id
    assert event.action == "client_folder.created"
    assert event.resource_type == "client_folder"


async def test_get_returns_none_for_unknown_id() -> None:
    _requires_disposable_sqlite()
    async with get_session_factory()() as session:
        found = await SqlAlchemyClientFolderRepository(session).get(id=uuid4())

    assert found is None


async def test_search_orders_by_name_and_supports_cursor_and_query() -> None:
    _requires_disposable_sqlite()
    marker = uuid4().hex[:8]
    names = [f"Ana Souza {marker}", f"Bruno Lima {marker}", f"Carlos Alves {marker}"]
    async with get_session_factory()() as session:
        repository = SqlAlchemyClientFolderRepository(session)
        for name in names:
            await repository.create(display_name=name, profile_data={})
        await session.commit()

    async with get_session_factory()() as session:
        repository = SqlAlchemyClientFolderRepository(session)
        first_page = await repository.search(query=marker, limit=2, before=None)
        assert [folder.display_name for folder in first_page] == names[:2]

        cursor = ClientFolderCursor(
            display_name=first_page[-1].display_name, id=first_page[-1].id
        )
        second_page = await repository.search(query=marker, limit=2, before=cursor)
        assert [folder.display_name for folder in second_page] == names[2:]

        filtered = await repository.search(
            query=f"ana souza {marker}", limit=10, before=None
        )
        assert [folder.display_name for folder in filtered] == names[:1]


async def test_update_changes_name_and_profile_data() -> None:
    _requires_disposable_sqlite()
    async with get_session_factory()() as session:
        created = await SqlAlchemyClientFolderRepository(session).create(
            display_name="Nome Antigo", profile_data={}
        )
        await session.commit()

    async with get_session_factory()() as session:
        repository = SqlAlchemyClientFolderRepository(session)
        updated = await repository.update(
            id=created.id,
            display_name="Nome Novo",
            profile_data={"telefone": "123"},
        )
        await session.commit()

    assert updated is not None
    assert updated.display_name == "Nome Novo"
    assert updated.profile_data == {"telefone": "123"}

    async with get_session_factory()() as session:
        stored = await session.scalar(
            select(ClientFolderModel).where(ClientFolderModel.id == created.id)
        )
    assert stored is not None
    assert stored.display_name == "Nome Novo"


async def test_update_returns_none_for_unknown_id() -> None:
    _requires_disposable_sqlite()
    async with get_session_factory()() as session:
        result = await SqlAlchemyClientFolderRepository(session).update(
            id=uuid4(), display_name="Alguém", profile_data={}
        )

    assert result is None


async def test_update_rejects_blank_identifying_name() -> None:
    _requires_disposable_sqlite()
    async with get_session_factory()() as session:
        created = await SqlAlchemyClientFolderRepository(session).create(
            display_name="Nome Válido", profile_data={}
        )
        await session.commit()

    async with get_session_factory()() as session:
        repository = SqlAlchemyClientFolderRepository(session)
        with pytest.raises(IntegrityError):
            await repository.update(id=created.id, display_name="  ", profile_data={})
