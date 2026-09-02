"""O caso de uso da ficha renderiza a pasta existente e audita a exportação (#34)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.clients.export_client_profile import (
    ExportClientProfileUseCase,
)
from crm_api.domain.audit.entities import AuditEvent, AuditResult
from crm_api.domain.clients.entities import ClientFolder
from crm_api.domain.clients.errors import ClientFolderNotFoundError
from crm_api.domain.clients.reporting import ClientProfileDocument

ACTOR_ID = UUID("00000000-0000-0000-0000-000000000017")


def _folder() -> ClientFolder:
    return ClientFolder(
        id=uuid4(),
        display_name="Ana Souza",
        profile_data={"telefone": "11 99999-0000"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@dataclass
class _MemoryRepository:
    folder: ClientFolder | None

    async def get(self, *, id: UUID) -> ClientFolder | None:
        if self.folder is not None and id == self.folder.id:
            return self.folder
        return None


@dataclass
class _RecordingRenderer:
    seen: list[ClientProfileDocument] = field(default_factory=list)

    def render(self, document: ClientProfileDocument) -> bytes:
        self.seen.append(document)
        return b"%PDF-stub"


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


def _use_case(
    folder: ClientFolder | None,
) -> tuple[
    ExportClientProfileUseCase,
    _RecordingRenderer,
    _RecordingAuditRepository,
    _SpyTransaction,
]:
    renderer = _RecordingRenderer()
    audit_repository = _RecordingAuditRepository()
    transaction = _SpyTransaction()
    use_case = ExportClientProfileUseCase(
        clients=_MemoryRepository(folder),
        renderer=renderer,
        audit=RecordAuditEventUseCase(events=audit_repository),
        transaction=transaction,
    )
    return use_case, renderer, audit_repository, transaction


async def test_renders_the_folder_and_audits_the_export() -> None:
    folder = _folder()
    use_case, renderer, audit, transaction = _use_case(folder)

    export = await use_case.execute(actor_user_id=ACTOR_ID, client_id=folder.id)

    assert export.display_name == "Ana Souza"
    assert export.pdf_bytes == b"%PDF-stub"
    assert renderer.seen[0] == ClientProfileDocument.from_folder(folder)
    assert audit.events[-1].action == "client_folder.profile_exported"
    assert audit.events[-1].resource_id == str(folder.id)
    assert audit.events[-1].result is AuditResult.SUCCESS
    assert transaction.commit_calls == 1


async def test_unknown_folder_is_not_audited() -> None:
    use_case, renderer, audit, transaction = _use_case(None)

    with pytest.raises(ClientFolderNotFoundError):
        await use_case.execute(actor_user_id=ACTOR_ID, client_id=uuid4())

    assert renderer.seen == []
    assert audit.events == []
    assert transaction.commit_calls == 0
