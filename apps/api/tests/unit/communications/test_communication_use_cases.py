"""Casos de uso de modelos e seleção sem transporte externo."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

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
from crm_api.domain.communications.entities import MessageTemplate, RecipientCandidate
from crm_api.domain.communications.errors import MessageTemplateNotFoundError
from crm_api.domain.documents.entities import DocumentStatus
from crm_api.presentation.communications.routes import router as communications_router

ACTOR_ID = UUID("00000000-0000-0000-0000-000000000024")


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
        self, *, document_status: DocumentStatus, limit: int
    ) -> list[RecipientCandidate]:
        return [
            item for item in self.candidates if item.document_status is document_status
        ][:limit]


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
    repository, _, _ = _dependencies()
    repository.candidates.append(
        RecipientCandidate(
            client_id=uuid4(),
            display_name="Cliente Sintético",
            document_status=DocumentStatus.PENDING,
            matching_documents=2,
        )
    )
    use_case = ListRecipientCandidatesUseCase(
        repository=repository  # type: ignore[arg-type]
    )

    candidates = await use_case.execute(
        document_status=DocumentStatus.PENDING, limit=10
    )
    assert candidates == repository.candidates

    with pytest.raises(ValueError, match="pending document status"):
        await use_case.execute(
            document_status=DocumentStatus.RECEIVED_REGULAR, limit=10
        )


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
