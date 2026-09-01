from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Mapping
from uuid import UUID, uuid4

import pytest

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.clients.update_client_folder import (
    UpdateClientFolderUseCase,
)
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditEvent,
    AuditEventCursor,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.clients.entities import ClientFolder, ClientFolderCursor
from crm_api.domain.clients.errors import ClientFolderNotFoundError


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
    folders: dict[UUID, ClientFolder] = field(default_factory=dict)
    update_calls: int = 0

    async def get(self, *, id: UUID) -> ClientFolder | None:
        return self.folders.get(id)

    async def search(
        self,
        *,
        query: str | None,
        limit: int,
        before: ClientFolderCursor | None,
    ) -> list[ClientFolder]:
        del query, limit, before
        return []

    async def update(
        self, *, id: UUID, display_name: str, profile_data: Mapping[str, str]
    ) -> ClientFolder | None:
        self.update_calls += 1
        existing = self.folders.get(id)
        if existing is None:
            return None
        updated = ClientFolder(
            id=existing.id,
            display_name=display_name,
            profile_data=profile_data,
            created_at=existing.created_at,
            updated_at=datetime.now(UTC),
        )
        self.folders[id] = updated
        return updated


def _build_use_case(
    folders: dict[UUID, ClientFolder] | None = None,
) -> tuple[
    UpdateClientFolderUseCase,
    FakeClientFolderRepository,
    FakeAuditEventRepository,
    FakeTransaction,
]:
    clients = FakeClientFolderRepository(folders=folders or {})
    events = FakeAuditEventRepository()
    transaction = FakeTransaction()
    return (
        UpdateClientFolderUseCase(
            clients=clients,
            audit=RecordAuditEventUseCase(events=events),
            transaction=transaction,
        ),
        clients,
        events,
        transaction,
    )


def _existing_folder() -> ClientFolder:
    return ClientFolder(
        id=uuid4(),
        display_name="Nome Antigo",
        profile_data={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


async def test_update_folder_normalizes_name_and_audits_the_action() -> None:
    folder = _existing_folder()
    use_case, _, events, transaction = _build_use_case({folder.id: folder})
    actor_id = UUID("00000000-0000-0000-0000-000000000001")

    updated = await use_case.execute(
        actor_user_id=actor_id,
        client_id=folder.id,
        display_name="  Novo   Nome ",
        profile_data={"telefone": "123"},
    )

    assert updated.display_name == "Novo Nome"
    assert updated.profile_data == {"telefone": "123"}
    assert transaction.commit_calls == 1
    assert events.events[0].actor_user_id == actor_id
    assert events.events[0].action is AuditAction.CLIENT_FOLDER_UPDATED
    assert events.events[0].resource_type is AuditResourceType.CLIENT_FOLDER
    assert events.events[0].resource_id == str(folder.id)


async def test_update_folder_raises_not_found_without_auditing() -> None:
    use_case, clients, events, transaction = _build_use_case()

    with pytest.raises(ClientFolderNotFoundError):
        await use_case.execute(
            actor_user_id=uuid4(), client_id=uuid4(), display_name="Alguém"
        )

    assert clients.update_calls == 1
    assert events.events == []
    assert transaction.commit_calls == 0
    assert transaction.rollback_calls == 0


@pytest.mark.parametrize("display_name", ["", "  ", 12])
async def test_update_folder_rejects_missing_or_invalid_name(
    display_name: object,
) -> None:
    folder = _existing_folder()
    use_case, clients, events, transaction = _build_use_case({folder.id: folder})

    with pytest.raises(ValueError, match="display_name"):
        await use_case.execute(
            actor_user_id=uuid4(),
            client_id=folder.id,
            display_name=display_name,  # type: ignore[arg-type]
        )

    assert clients.update_calls == 0
    assert events.events == []
    assert transaction.commit_calls == 0
    assert transaction.rollback_calls == 0
