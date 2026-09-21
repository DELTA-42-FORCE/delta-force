from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.communications.render_template import (
    RenderMessageTemplateUseCase,
)
from crm_api.application.communications.templates import normalize_template_fields
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditEvent,
    AuditEventCursor,
    AuditResult,
)
from crm_api.domain.clients.entities import ClientFolder
from crm_api.domain.clients.errors import ClientFolderNotFoundError
from crm_api.domain.communications.entities import MessageTemplate
from crm_api.domain.communications.errors import MessageTemplateNotFoundError


@dataclass
class FakeTemplates:
    template: MessageTemplate | None

    async def get_template(self, *, id: UUID) -> MessageTemplate | None:
        if self.template is not None and self.template.id == id:
            return self.template
        return None


@dataclass
class FakeClients:
    client: ClientFolder | None

    async def get(self, *, id: UUID) -> ClientFolder | None:
        if self.client is not None and self.client.id == id:
            return self.client
        return None


@dataclass
class FakeAuditEvents:
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


def _use_case(
    *, template: MessageTemplate | None, client: ClientFolder | None
) -> tuple[RenderMessageTemplateUseCase, FakeAuditEvents, FakeTransaction]:
    events = FakeAuditEvents()
    transaction = FakeTransaction()
    return (
        RenderMessageTemplateUseCase(
            templates=FakeTemplates(template),  # type: ignore[arg-type]
            clients=FakeClients(client),  # type: ignore[arg-type]
            audit=RecordAuditEventUseCase(events=events),
            transaction=transaction,
        ),
        events,
        transaction,
    )


def _template() -> MessageTemplate:
    now = datetime.now(UTC)
    return MessageTemplate(
        id=uuid4(),
        name="Pendência",
        subject="Olá, {{nome}}",
        body="Olá, {{nome}}. Existe uma pendência documental.",
        created_at=now,
        updated_at=now,
    )


def _client() -> ClientFolder:
    now = datetime.now(UTC)
    return ClientFolder(
        id=uuid4(),
        display_name="Cliente Sintético",
        email="cliente@example.com",
        profile_data={},
        created_at=now,
        updated_at=now,
    )


async def test_render_replaces_only_the_homologated_name_variable() -> None:
    template = _template()
    client = _client()
    use_case, events, transaction = _use_case(template=template, client=client)
    actor_id = uuid4()
    rendered = await use_case.execute(
        actor_user_id=actor_id,
        template_id=template.id,
        client_id=client.id,
    )

    assert rendered.subject == "Olá, Cliente Sintético"
    assert rendered.body == ("Olá, Cliente Sintético. Existe uma pendência documental.")
    assert transaction.commit_calls == 1
    assert events.events[0].actor_user_id == actor_id
    assert events.events[0].action is AuditAction.CLIENT_FOLDER_VIEWED
    assert events.events[0].resource_id == str(client.id)


async def test_render_rejects_unknown_template_or_client() -> None:
    template = _template()
    client = _client()
    missing_template, _, missing_template_transaction = _use_case(
        template=None, client=client
    )
    with pytest.raises(MessageTemplateNotFoundError):
        await missing_template.execute(
            actor_user_id=uuid4(), template_id=template.id, client_id=client.id
        )
    assert missing_template_transaction.rollback_calls == 1
    missing_client, _, missing_client_transaction = _use_case(
        template=template, client=None
    )
    with pytest.raises(ClientFolderNotFoundError):
        await missing_client.execute(
            actor_user_id=uuid4(), template_id=template.id, client_id=client.id
        )
    assert missing_client_transaction.rollback_calls == 1


def test_template_normalization_rejects_unapproved_variables() -> None:
    with pytest.raises(ValueError, match="unsupported variables: cpf"):
        normalize_template_fields(
            name="Exemplo",
            subject="Olá, {{nome}}",
            body="CPF: {{cpf}}",
        )


def test_template_normalization_canonicalizes_and_rejects_malformed_variables() -> None:
    _, subject, body = normalize_template_fields(
        name="Exemplo",
        subject="Olá, {{ nome }}",
        body="Prezado {{nome}}, confira a documentação.",
    )

    assert subject == "Olá, {{nome}}"
    assert body == "Prezado {{nome}}, confira a documentação."

    with pytest.raises(ValueError, match="malformed variables"):
        normalize_template_fields(
            name="Exemplo",
            subject="Olá",
            body="Prezado {{nome, confira a documentação.",
        )


def test_template_normalization_rejects_multiline_subject() -> None:
    with pytest.raises(ValueError, match="single line"):
        normalize_template_fields(
            name="Exemplo",
            subject="Linha 1\nLinha 2",
            body="Conteúdo seguro",
        )
