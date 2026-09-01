from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Mapping
from uuid import UUID, uuid4

import pytest

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.clients.create_client_folder import CreateClientFolderUseCase
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditEvent,
    AuditEventCursor,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.clients.entities import ClientFolder


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
    created: list[ClientFolder] = field(default_factory=list)

    async def create(
        self, *, display_name: str, profile_data: Mapping[str, str]
    ) -> ClientFolder:
        folder = ClientFolder(
            id=uuid4(),
            display_name=display_name,
            profile_data=profile_data,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.created.append(folder)
        return folder


def _build_use_case() -> tuple[
    CreateClientFolderUseCase,
    FakeClientFolderRepository,
    FakeAuditEventRepository,
    FakeTransaction,
]:
    clients = FakeClientFolderRepository()
    events = FakeAuditEventRepository()
    transaction = FakeTransaction()
    return (
        CreateClientFolderUseCase(
            clients=clients,
            audit=RecordAuditEventUseCase(events=events),
            transaction=transaction,
        ),
        clients,
        events,
        transaction,
    )


async def test_create_folder_requires_only_name_and_audits_the_action() -> None:
    use_case, clients, events, transaction = _build_use_case()
    actor_id = UUID("00000000-0000-0000-0000-000000000001")

    folder = await use_case.execute(
        actor_user_id=actor_id,
        display_name="  Maria   da  Silva ",
    )

    assert folder.display_name == "Maria da Silva"
    assert folder.profile_data == {}
    assert clients.created == [folder]
    assert transaction.commit_calls == 1
    assert events.events[0].actor_user_id == actor_id
    assert events.events[0].action is AuditAction.CLIENT_FOLDER_CREATED
    assert events.events[0].resource_type is AuditResourceType.CLIENT_FOLDER
    assert events.events[0].resource_id == str(folder.id)


@pytest.mark.parametrize("display_name", ["", "  ", 12])
async def test_create_folder_rejects_missing_or_invalid_name(
    display_name: object,
) -> None:
    use_case, clients, events, transaction = _build_use_case()

    with pytest.raises(ValueError, match="display_name"):
        await use_case.execute(
            actor_user_id=uuid4(),
            display_name=display_name,  # type: ignore[arg-type]
        )

    assert clients.created == []
    assert events.events == []
    assert transaction.commit_calls == 0
    assert transaction.rollback_calls == 0


async def test_create_folder_accepts_optional_flexible_profile_data() -> None:
    use_case, _, _, _ = _build_use_case()

    folder = await use_case.execute(
        actor_user_id=uuid4(),
        display_name="Cliente Sintético",
        profile_data={"telefone": "(92) 0000-0000", "anotação": "retornar depois"},
    )

    assert folder.profile_data == {
        "telefone": "(92) 0000-0000",
        "anotação": "retornar depois",
    }
