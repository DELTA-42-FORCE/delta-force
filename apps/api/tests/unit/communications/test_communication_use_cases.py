"""Casos de uso de modelos e seleção sem transporte externo."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.communications.list_recipient_candidates import (
    ListRecipientCandidatesUseCase,
)
from crm_api.application.communications.templates import (
    CreateMessageTemplateUseCase,
    DeleteMessageTemplateUseCase,
    UpdateMessageTemplateUseCase,
)
from crm_api.domain.audit.entities import AuditEvent
from crm_api.domain.auth.entities import User
from crm_api.domain.communications.entities import (
    MessageTemplate,
    RecipientCandidate,
    RecipientCandidateCursor,
)
from crm_api.domain.communications.errors import MessageTemplateNotFoundError
from crm_api.domain.documents.entities import DocumentStatus
from crm_api.presentation.communications.routes import router as communications_router
from crm_api.main import app
from crm_api.presentation.auth import dependencies as auth_dependencies
from crm_api.presentation.communications import (
    dependencies as communication_dependencies,
)

ACTOR_ID = UUID("00000000-0000-0000-0000-000000000024")
OWNER = User(
    id=ACTOR_ID,
    email="owner@communications.deltaforce.internal",
    full_name="Proprietário Sintético",
    password_hash="not-returned",
    is_active=True,
)


def _template() -> MessageTemplate:
    now = datetime.now(UTC)
    return MessageTemplate(
        id=uuid4(),
        name="Pendência",
        subject="Documentos pendentes",
        body="Entre em contato conosco.",
        created_at=now,
        updated_at=now,
    )


@dataclass
class _Repository:
    templates: dict[UUID, MessageTemplate] = field(default_factory=dict)
    candidates: list[RecipientCandidate] = field(default_factory=list)

    async def create_template(
        self, *, name: str, subject: str, body: str
    ) -> MessageTemplate:
        template = _template()
        template = replace(template, name=name, subject=subject, body=body)
        self.templates[template.id] = template
        return template

    async def list_templates(self) -> list[MessageTemplate]:
        return list(self.templates.values())

    async def get_template(self, *, id: UUID) -> MessageTemplate | None:
        return self.templates.get(id)

    async def update_template(
        self, *, id: UUID, name: str, subject: str, body: str
    ) -> MessageTemplate | None:
        current = self.templates.get(id)
        if current is None:
            return None
        updated = replace(
            current,
            name=name,
            subject=subject,
            body=body,
            updated_at=datetime.now(UTC),
        )
        self.templates[id] = updated
        return updated

    async def delete_template(self, *, id: UUID) -> bool:
        return self.templates.pop(id, None) is not None

    async def list_recipient_candidates(
        self,
        *,
        document_status: DocumentStatus,
        limit: int,
        before: RecipientCandidateCursor | None,
    ) -> list[RecipientCandidate]:
        candidates = sorted(
            (
                item
                for item in self.candidates
                if item.document_status is document_status
            ),
            key=lambda item: (item.display_name, item.client_id),
        )
        if before is not None:
            candidates = [
                item
                for item in candidates
                if (item.display_name, item.client_id)
                > (before.display_name, before.client_id)
            ]
        return candidates[:limit]


@dataclass
class _AuditRepository:
    events: list[AuditEvent] = field(default_factory=list)

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)


@dataclass
class _Transaction:
    commits: int = 0
    rollbacks: int = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _dependencies() -> tuple[_Repository, _AuditRepository, _Transaction]:
    return _Repository(), _AuditRepository(), _Transaction()


async def test_create_update_and_delete_are_audited_without_message_content() -> None:
    repository, events, transaction = _dependencies()
    audit = RecordAuditEventUseCase(events=events)  # type: ignore[arg-type]
    created = await CreateMessageTemplateUseCase(
        repository=repository,  # type: ignore[arg-type]
        audit=audit,
        transaction=transaction,
    ).execute(
        actor_user_id=ACTOR_ID,
        name="  Pendência documental  ",
        subject="  Documentos necessários  ",
        body="  Favor verificar a documentação.  ",
    )
    updated = await UpdateMessageTemplateUseCase(
        repository=repository,  # type: ignore[arg-type]
        audit=audit,
        transaction=transaction,
    ).execute(
        actor_user_id=ACTOR_ID,
        template_id=created.id,
        name="Incompleto",
        subject="Documento incompleto",
        body="Favor reenviar.",
    )
    await DeleteMessageTemplateUseCase(
        repository=repository,  # type: ignore[arg-type]
        audit=audit,
        transaction=transaction,
    ).execute(actor_user_id=ACTOR_ID, template_id=created.id)

    assert updated.name == "Incompleto"
    assert transaction.commits == 3
    assert [event.action.value for event in events.events] == [
        "message_template.created",
        "message_template.updated",
        "message_template.deleted",
    ]
    assert all(event.context == {} for event in events.events)
    assert "Favor" not in repr(events.events)


async def test_unknown_template_rolls_back_without_audit_event() -> None:
    repository, events, transaction = _dependencies()
    use_case = DeleteMessageTemplateUseCase(
        repository=repository,  # type: ignore[arg-type]
        audit=RecordAuditEventUseCase(events=events),  # type: ignore[arg-type]
        transaction=transaction,
    )

    with pytest.raises(MessageTemplateNotFoundError):
        await use_case.execute(actor_user_id=ACTOR_ID, template_id=uuid4())

    assert transaction.rollbacks == 1
    assert events.events == []


@pytest.mark.parametrize("field", ["name", "subject", "body"])
async def test_blank_template_field_is_rejected(field: str) -> None:
    repository, events, transaction = _dependencies()
    values = {
        "name": "Modelo",
        "subject": "Assunto",
        "body": "Mensagem",
    }
    values[field] = "   "

    with pytest.raises(ValueError, match=field):
        await CreateMessageTemplateUseCase(
            repository=repository,  # type: ignore[arg-type]
            audit=RecordAuditEventUseCase(events=events),  # type: ignore[arg-type]
            transaction=transaction,
        ).execute(actor_user_id=ACTOR_ID, **values)

    assert repository.templates == {}
    assert transaction.commits == 0


async def test_candidates_allow_only_actionable_document_statuses() -> None:
    repository, events, transaction = _dependencies()
    repository.candidates.append(
        RecipientCandidate(
            client_id=uuid4(),
            display_name="Cliente Sintético",
            document_status=DocumentStatus.PENDING,
            matching_documents=2,
        )
    )
    use_case = ListRecipientCandidatesUseCase(
        repository=repository,  # type: ignore[arg-type]
        audit=RecordAuditEventUseCase(events=events),  # type: ignore[arg-type]
        transaction=transaction,
    )

    page = await use_case.execute(
        actor_user_id=ACTOR_ID,
        document_status=DocumentStatus.PENDING,
        limit=10,
        before=None,
    )
    assert page.items == tuple(repository.candidates)
    assert page.next_cursor is None
    assert transaction.commits == 1
    assert len(events.events) == 1
    assert events.events[0].action.value == "recipient_candidates.viewed"
    assert events.events[0].resource_id is None
    assert events.events[0].context == {}

    with pytest.raises(ValueError, match="pending document status"):
        await use_case.execute(
            actor_user_id=ACTOR_ID,
            document_status=DocumentStatus.RECEIVED_REGULAR,
            limit=10,
            before=None,
        )


async def test_candidate_cursor_reaches_items_after_the_first_hundred() -> None:
    repository, events, transaction = _dependencies()
    repository.candidates.extend(
        RecipientCandidate(
            client_id=UUID(int=index + 1),
            display_name=f"Cliente Sintético {index:03d}",
            document_status=DocumentStatus.PENDING,
            matching_documents=1,
        )
        for index in range(101)
    )
    use_case = ListRecipientCandidatesUseCase(
        repository=repository,  # type: ignore[arg-type]
        audit=RecordAuditEventUseCase(events=events),  # type: ignore[arg-type]
        transaction=transaction,
    )

    first_page = await use_case.execute(
        actor_user_id=ACTOR_ID,
        document_status=DocumentStatus.PENDING,
        limit=100,
        before=None,
    )
    assert len(first_page.items) == 100
    assert first_page.next_cursor == RecipientCandidateCursor(
        display_name="Cliente Sintético 099",
        client_id=UUID(int=100),
    )

    second_page = await use_case.execute(
        actor_user_id=ACTOR_ID,
        document_status=DocumentStatus.PENDING,
        limit=100,
        before=first_page.next_cursor,
    )

    assert [item.display_name for item in second_page.items] == [
        "Cliente Sintético 100"
    ]
    assert second_page.next_cursor is None
    assert transaction.commits == 2
    assert [event.action.value for event in events.events] == [
        "recipient_candidates.viewed",
        "recipient_candidates.viewed",
    ]
    assert all(event.context == {} for event in events.events)


def test_candidate_http_cursor_reaches_items_after_the_first_hundred() -> None:
    repository, events, transaction = _dependencies()
    repository.candidates.extend(
        RecipientCandidate(
            client_id=UUID(int=index + 1),
            display_name=f"Cliente Sintético {index:03d}",
            document_status=DocumentStatus.PENDING,
            matching_documents=1,
        )
        for index in range(101)
    )
    use_case = ListRecipientCandidatesUseCase(
        repository=repository,  # type: ignore[arg-type]
        audit=RecordAuditEventUseCase(events=events),  # type: ignore[arg-type]
        transaction=transaction,
    )
    app.dependency_overrides[auth_dependencies.get_current_user] = lambda: OWNER
    app.dependency_overrides[
        communication_dependencies.get_list_recipient_candidates_use_case
    ] = lambda: use_case

    try:
        with TestClient(app) as client:
            first_response = client.get(
                "/email-recipient-candidates",
                params={"status": "pending", "limit": 100},
            )
            assert first_response.status_code == 200
            first_page = first_response.json()
            assert len(first_page["items"]) == 100
            assert first_page["next_cursor"] == {
                "display_name": "Cliente Sintético 099",
                "client_id": str(UUID(int=100)),
            }

            second_response = client.get(
                "/email-recipient-candidates",
                params={
                    "status": "pending",
                    "limit": 100,
                    "before_display_name": first_page["next_cursor"]["display_name"],
                    "before_client_id": first_page["next_cursor"]["client_id"],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert second_response.status_code == 200
    assert [item["display_name"] for item in second_response.json()["items"]] == [
        "Cliente Sintético 100"
    ]
    assert second_response.json()["next_cursor"] is None
    assert transaction.commits == 2
    assert len(events.events) == 2
    assert all(event.context == {} for event in events.events)


def test_every_communication_route_requires_the_authenticated_owner() -> None:
    routes = list(communications_router.routes)

    assert len(routes) == 5
    for route in routes:
        dependants = route.dependant.dependencies  # type: ignore[attr-defined]
        dependency_names = {
            dependant.call.__name__
            for dependant in dependants
            if dependant.call is not None
        }
        assert "get_current_user" in dependency_names
