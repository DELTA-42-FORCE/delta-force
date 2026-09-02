"""Contrato HTTP das rotas autenticadas da pasta flexível de clientes."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Mapping
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.clients.create_client_folder import (
    CreateClientFolderUseCase,
)
from crm_api.application.clients.export_client_profile import (
    ExportClientProfileUseCase,
)
from crm_api.application.clients.get_client_folder import GetClientFolderUseCase
from crm_api.application.clients.list_client_folders import (
    ListClientFoldersUseCase,
)
from crm_api.application.clients.update_client_folder import (
    UpdateClientFolderUseCase,
)
from crm_api.domain.audit.entities import AuditEvent
from crm_api.domain.auth.entities import User
from crm_api.domain.clients.entities import ClientFolder, ClientFolderCursor
from crm_api.infrastructure.reporting.client_profile_pdf import (
    MinimalClientProfilePdfRenderer,
)
from crm_api.main import app
from crm_api.presentation.auth import dependencies as auth_dependencies
from crm_api.presentation.clients import dependencies as client_dependencies

OWNER_ID = UUID("00000000-0000-0000-0000-000000000017")
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
        self.folders[folder.id] = folder
        return folder

    async def get(self, *, id: UUID) -> ClientFolder | None:
        return self.folders.get(id)

    async def search(
        self,
        *,
        query: str | None,
        limit: int,
        before: ClientFolderCursor | None,
    ) -> list[ClientFolder]:
        ordered = sorted(
            self.folders.values(), key=lambda folder: (folder.display_name, folder.id)
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


@dataclass
class SpyTransaction:
    commit_calls: int = 0
    rollback_calls: int = 0

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


@pytest.fixture
def client_fixture() -> (
    Iterator[
        tuple[
            TestClient, MemoryClientFolderRepository, list[AuditEvent], SpyTransaction
        ]
    ]
):
    repository = MemoryClientFolderRepository()
    events: list[AuditEvent] = []

    @dataclass
    class RecordingAuditRepository:
        async def append(self, event: AuditEvent) -> None:
            events.append(event)

        async def list_recent(self, **_: object) -> list[AuditEvent]:
            return []

    transaction = SpyTransaction()
    audit = RecordAuditEventUseCase(events=RecordingAuditRepository())

    app.dependency_overrides[auth_dependencies.get_current_user] = lambda: OWNER
    app.dependency_overrides[client_dependencies.get_create_client_folder_use_case] = (
        lambda: CreateClientFolderUseCase(
            clients=repository, audit=audit, transaction=transaction
        )
    )
    app.dependency_overrides[client_dependencies.get_get_client_folder_use_case] = (
        lambda: GetClientFolderUseCase(
            clients=repository, audit=audit, transaction=transaction
        )
    )
    app.dependency_overrides[client_dependencies.get_list_client_folders_use_case] = (
        lambda: ListClientFoldersUseCase(
            clients=repository, audit=audit, transaction=transaction
        )
    )
    app.dependency_overrides[client_dependencies.get_update_client_folder_use_case] = (
        lambda: UpdateClientFolderUseCase(
            clients=repository, audit=audit, transaction=transaction
        )
    )
    app.dependency_overrides[client_dependencies.get_export_client_profile_use_case] = (
        lambda: ExportClientProfileUseCase(
            clients=repository,
            renderer=MinimalClientProfilePdfRenderer(),
            audit=audit,
            transaction=transaction,
        )
    )

    try:
        with TestClient(app) as test_client:
            yield test_client, repository, events, transaction
    finally:
        app.dependency_overrides.clear()


def test_owner_creates_a_client_folder_with_only_a_name(
    client_fixture: tuple[
        TestClient, MemoryClientFolderRepository, list[AuditEvent], SpyTransaction
    ],
) -> None:
    client, _, events, transaction = client_fixture

    response = client.post("/clients", json={"display_name": "Maria da Silva"})

    assert response.status_code == 201
    body = response.json()
    assert body["display_name"] == "Maria da Silva"
    assert body["profile_data"] == {}
    assert events[-1].action == "client_folder.created"
    assert transaction.commit_calls == 1


def test_create_rejects_blank_name(
    client_fixture: tuple[
        TestClient, MemoryClientFolderRepository, list[AuditEvent], SpyTransaction
    ],
) -> None:
    client, _, events, transaction = client_fixture

    response = client.post("/clients", json={"display_name": "   "})

    assert response.status_code == 422
    assert events == []
    assert transaction.commit_calls == 0


def test_owner_lists_and_searches_folders_with_stable_pagination(
    client_fixture: tuple[
        TestClient, MemoryClientFolderRepository, list[AuditEvent], SpyTransaction
    ],
) -> None:
    client, _, events, _ = client_fixture
    client.post("/clients", json={"display_name": "Ana Souza"})
    client.post("/clients", json={"display_name": "Bruno Lima"})
    events.clear()

    response = client.get("/clients", params={"limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["display_name"] == "Ana Souza"
    assert body["next_cursor"] == {
        "display_name": "Ana Souza",
        "id": body["items"][0]["id"],
    }
    assert events[-1].action == "client_folder.viewed"
    assert events[-1].resource_id is None

    second_page = client.get(
        "/clients",
        params={
            "limit": 1,
            "before_display_name": body["next_cursor"]["display_name"],
            "before_id": body["next_cursor"]["id"],
        },
    )
    assert second_page.json()["items"][0]["display_name"] == "Bruno Lima"
    assert second_page.json()["next_cursor"] is None


def test_search_query_filters_by_name(
    client_fixture: tuple[
        TestClient, MemoryClientFolderRepository, list[AuditEvent], SpyTransaction
    ],
) -> None:
    client, _, _, _ = client_fixture
    client.post("/clients", json={"display_name": "Ana Souza"})
    client.post("/clients", json={"display_name": "Bruno Lima"})

    response = client.get("/clients", params={"query": "ana"})

    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["display_name"] == "Ana Souza"


def test_owner_gets_a_folder_and_audits_the_view(
    client_fixture: tuple[
        TestClient, MemoryClientFolderRepository, list[AuditEvent], SpyTransaction
    ],
) -> None:
    client, _, events, _ = client_fixture
    created = client.post("/clients", json={"display_name": "Ana Souza"}).json()
    events.clear()

    response = client.get(f"/clients/{created['id']}")

    assert response.status_code == 200
    assert response.json()["display_name"] == "Ana Souza"
    assert events[-1].action == "client_folder.viewed"
    assert events[-1].resource_id == created["id"]


def test_get_unknown_folder_returns_404(
    client_fixture: tuple[
        TestClient, MemoryClientFolderRepository, list[AuditEvent], SpyTransaction
    ],
) -> None:
    client, _, events, transaction = client_fixture

    response = client.get(f"/clients/{uuid4()}")

    assert response.status_code == 404
    assert events == []
    assert transaction.commit_calls == 0


def test_owner_updates_a_folder_and_audits_the_change(
    client_fixture: tuple[
        TestClient, MemoryClientFolderRepository, list[AuditEvent], SpyTransaction
    ],
) -> None:
    client, _, events, _ = client_fixture
    created = client.post("/clients", json={"display_name": "Ana Souza"}).json()
    events.clear()

    response = client.put(
        f"/clients/{created['id']}",
        json={"display_name": "Ana Souza Lima", "profile_data": {"telefone": "123"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Ana Souza Lima"
    assert body["profile_data"] == {"telefone": "123"}
    assert events[-1].action == "client_folder.updated"
    assert events[-1].resource_id == created["id"]


def test_update_unknown_folder_returns_404(
    client_fixture: tuple[
        TestClient, MemoryClientFolderRepository, list[AuditEvent], SpyTransaction
    ],
) -> None:
    client, _, events, transaction = client_fixture

    response = client.put(f"/clients/{uuid4()}", json={"display_name": "Alguém"})

    assert response.status_code == 404
    assert events == []
    assert transaction.commit_calls == 0


def test_owner_exports_the_client_profile_as_pdf(
    client_fixture: tuple[
        TestClient, MemoryClientFolderRepository, list[AuditEvent], SpyTransaction
    ],
) -> None:
    client, _, events, transaction = client_fixture
    created = client.post(
        "/clients",
        json={
            "display_name": "Ana Souza",
            "profile_data": {"telefone": "11 99999-0000", "cidade": "São Paulo"},
        },
    ).json()
    events.clear()
    transaction.commit_calls = 0

    response = client.get(f"/clients/{created['id']}/profile.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert response.content.rstrip().endswith(b"%%EOF")
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert "ficha-cadastral-ana-souza.pdf" in disposition
    assert response.headers["x-content-type-options"] == "nosniff"
    assert events[-1].action == "client_folder.profile_exported"
    assert events[-1].resource_id == created["id"]
    assert events[-1].result == "success"
    assert transaction.commit_calls == 1


def test_profile_pdf_is_generated_even_without_optional_fields(
    client_fixture: tuple[
        TestClient, MemoryClientFolderRepository, list[AuditEvent], SpyTransaction
    ],
) -> None:
    client, _, _, _ = client_fixture
    created = client.post(
        "/clients", json={"display_name": "Cliente Sem Campos"}
    ).json()

    response = client.get(f"/clients/{created['id']}/profile.pdf")

    # A ausência de qualquer campo opcional nunca impede a geração da ficha.
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")


def test_export_profile_of_unknown_folder_returns_404(
    client_fixture: tuple[
        TestClient, MemoryClientFolderRepository, list[AuditEvent], SpyTransaction
    ],
) -> None:
    client, _, events, transaction = client_fixture

    response = client.get(f"/clients/{uuid4()}/profile.pdf")

    assert response.status_code == 404
    assert response.json()["detail"] == "client folder not found"
    assert events == []
    assert transaction.commit_calls == 0


@pytest.mark.parametrize(
    "params",
    [
        {"before_id": "00000000-0000-0000-0000-000000000002"},
        {"before_display_name": "Ana"},
    ],
)
def test_invalid_cursor_pairing_is_rejected(
    client_fixture: tuple[
        TestClient, MemoryClientFolderRepository, list[AuditEvent], SpyTransaction
    ],
    params: dict[str, str],
) -> None:
    client, _, events, transaction = client_fixture

    response = client.get("/clients", params=params)

    assert response.status_code == 422
    assert events == []
    assert transaction.commit_calls == 0


def test_client_response_never_exposes_authentication_material(
    client_fixture: tuple[
        TestClient, MemoryClientFolderRepository, list[AuditEvent], SpyTransaction
    ],
) -> None:
    client, _, _, _ = client_fixture
    client.post("/clients", json={"display_name": "Ana Souza"})

    response = client.get("/clients")

    serialized = response.text.lower()
    assert "password" not in serialized
    assert "session_token" not in serialized
    assert "authorization" not in serialized
