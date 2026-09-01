from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Mapping
from uuid import UUID, uuid4

import pytest

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.clients.list_client_folders import (
    ListClientFoldersUseCase,
)
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditEvent,
    AuditEventCursor,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.clients.entities import ClientFolder, ClientFolderCursor


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


def _make_folder(display_name: str) -> ClientFolder:
    return ClientFolder(
        id=uuid4(),
        display_name=display_name,
        profile_data={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@dataclass
class FakeClientFolderRepository:
    folders: list[ClientFolder] = field(default_factory=list)
    last_search: dict[str, object] | None = None

    async def get(self, *, id: UUID) -> ClientFolder | None:
        return next((folder for folder in self.folders if folder.id == id), None)

    async def search(
        self,
        *,
        query: str | None,
        limit: int,
        before: ClientFolderCursor | None,
    ) -> list[ClientFolder]:
        self.last_search = {"query": query, "limit": limit, "before": before}
        ordered = sorted(
            self.folders, key=lambda folder: (folder.display_name, folder.id)
        )
        if before is not None:
            ordered = [
                folder
                for folder in ordered
                if (folder.display_name, folder.id) > (before.display_name, before.id)
            ]
        if query:
            ordered = [
                folder
                for folder in ordered
                if query.lower() in folder.display_name.lower()
            ]
        return ordered[:limit]

    async def update(
        self, *, id: UUID, display_name: str, profile_data: Mapping[str, str]
    ) -> ClientFolder | None:
        del display_name, profile_data
        return next((folder for folder in self.folders if folder.id == id), None)


def _build_use_case(
    folders: list[ClientFolder] | None = None,
) -> tuple[
    ListClientFoldersUseCase,
    FakeClientFolderRepository,
    FakeAuditEventRepository,
    FakeTransaction,
]:
    clients = FakeClientFolderRepository(folders=folders or [])
    events = FakeAuditEventRepository()
    transaction = FakeTransaction()
    return (
        ListClientFoldersUseCase(
            clients=clients,
            audit=RecordAuditEventUseCase(events=events),
            transaction=transaction,
        ),
        clients,
        events,
        transaction,
    )


async def test_list_folders_returns_page_and_audits_a_single_view() -> None:
    folders = [_make_folder("Ana"), _make_folder("Bruno"), _make_folder("Carlos")]
    use_case, _, events, transaction = _build_use_case(folders)
    actor_id = UUID("00000000-0000-0000-0000-000000000001")

    page = await use_case.execute(actor_user_id=actor_id, limit=2, before=None)

    assert [folder.display_name for folder in page.items] == ["Ana", "Bruno"]
    assert page.next_cursor is not None
    assert page.next_cursor.display_name == "Bruno"
    assert transaction.commit_calls == 1
    assert len(events.events) == 1
    assert events.events[0].actor_user_id == actor_id
    assert events.events[0].action is AuditAction.CLIENT_FOLDER_VIEWED
    assert events.events[0].resource_type is AuditResourceType.CLIENT_FOLDER
    assert events.events[0].resource_id is None


async def test_list_folders_last_page_has_no_next_cursor() -> None:
    folders = [_make_folder("Ana"), _make_folder("Bruno")]
    use_case, _, _, _ = _build_use_case(folders)

    page = await use_case.execute(actor_user_id=uuid4(), limit=10, before=None)

    assert len(page.items) == 2
    assert page.next_cursor is None


async def test_list_folders_forwards_query_filter() -> None:
    folders = [_make_folder("Ana Souza"), _make_folder("Bruno Lima")]
    use_case, clients, _, _ = _build_use_case(folders)

    page = await use_case.execute(
        actor_user_id=uuid4(), limit=10, before=None, query="ana"
    )

    assert [folder.display_name for folder in page.items] == ["Ana Souza"]
    assert clients.last_search is not None
    assert clients.last_search["query"] == "ana"


@pytest.mark.parametrize("limit", [0, 101])
async def test_list_folders_rejects_limit_out_of_range(limit: int) -> None:
    use_case, _, events, transaction = _build_use_case()

    with pytest.raises(ValueError, match="limit"):
        await use_case.execute(actor_user_id=uuid4(), limit=limit, before=None)

    assert events.events == []
    assert transaction.commit_calls == 0
    assert transaction.rollback_calls == 0
