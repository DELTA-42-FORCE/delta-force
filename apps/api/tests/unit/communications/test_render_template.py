from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from crm_api.application.communications.render_template import (
    RenderMessageTemplateUseCase,
)
from crm_api.application.communications.templates import normalize_template_fields
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
    rendered = await RenderMessageTemplateUseCase(
        templates=FakeTemplates(template),  # type: ignore[arg-type]
        clients=FakeClients(client),  # type: ignore[arg-type]
    ).execute(template_id=template.id, client_id=client.id)

    assert rendered.subject == "Olá, Cliente Sintético"
    assert rendered.body == ("Olá, Cliente Sintético. Existe uma pendência documental.")


async def test_render_rejects_unknown_template_or_client() -> None:
    template = _template()
    client = _client()
    with pytest.raises(MessageTemplateNotFoundError):
        await RenderMessageTemplateUseCase(
            templates=FakeTemplates(None),  # type: ignore[arg-type]
            clients=FakeClients(client),  # type: ignore[arg-type]
        ).execute(template_id=template.id, client_id=client.id)
    with pytest.raises(ClientFolderNotFoundError):
        await RenderMessageTemplateUseCase(
            templates=FakeTemplates(template),  # type: ignore[arg-type]
            clients=FakeClients(None),  # type: ignore[arg-type]
        ).execute(template_id=template.id, client_id=client.id)


def test_template_normalization_rejects_unapproved_variables() -> None:
    with pytest.raises(ValueError, match="unsupported variables: cpf"):
        normalize_template_fields(
            name="Exemplo",
            subject="Olá, {{nome}}",
            body="CPF: {{cpf}}",
        )
