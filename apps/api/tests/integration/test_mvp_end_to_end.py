"""E2E do fluxo operacional do MVP (#27), encadeado pela API HTTP.

Cobre primeiro acesso, login, cadastro de cliente, anexo/consulta/exportação de
documento, ficha cadastral em PDF, importação do acervo legado, classificação
documental, modelos, triagem, envio individual, histórico e auditoria com dados
sintéticos. O transporte é substituído por um falso: nenhum e-mail sai do teste.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.communications.email_delivery import SendEmailBatchUseCase
from crm_api.domain.communications.entities import (
    EmailDeliveryResult,
    EmailDeliveryStatus,
    EmailSenderSettings,
    OutboundEmail,
)
from crm_api.infrastructure.audit.repositories import SqlAlchemyAuditEventRepository
from crm_api.infrastructure.audit.transactions import SqlAlchemyTransaction
from crm_api.infrastructure.audit.models import AuditEventModel
from crm_api.infrastructure.auth.models import OwnerSlotModel, SessionModel, UserModel
from crm_api.infrastructure.clients.models import ClientFolderModel
from crm_api.infrastructure.clients.repositories import SqlAlchemyClientFolderRepository
from crm_api.infrastructure.communications.models import (
    EmailDispatchModel,
    EmailSenderSettingsModel,
    MessageTemplateModel,
)
from crm_api.infrastructure.communications.repositories import (
    SqlAlchemyCommunicationRepository,
)
from crm_api.infrastructure.database import get_engine, get_session_factory
from crm_api.infrastructure.documents.models import DocumentModel
from crm_api.main import app
from crm_api.presentation.communications.dependencies import (
    get_send_email_batch_use_case,
)
from crm_api.presentation.dependencies import DatabaseSession

pytestmark = pytest.mark.integration

# PDF mínimo íntegro, aceito pela validação de conteúdo de documentos.
PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"
# Um segundo PDF com conteúdo distinto, para o import não deduplicar contra o
# documento já anexado ao mesmo cliente (a deduplicação é por checksum).
LEGACY_PDF_BYTES = (
    b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Legacy true >>\nendobj\ntrailer\n%%EOF\n"
)


def _is_disposable_sqlite() -> bool:
    engine = get_engine()
    if engine.dialect.name != "sqlite":
        return False
    return Path(engine.url.database or "").stem.startswith("delta_force_integration_")


def _requires_disposable_sqlite() -> None:
    """Este E2E escreve documentos e importa arquivos; só roda em banco descartável."""
    engine = get_engine()
    if engine.dialect.name != "sqlite":
        pytest.skip("requires a sqlite+aiosqlite DATABASE_URL")
    if not _is_disposable_sqlite():
        raise RuntimeError("refusing E2E test on non-disposable SQLite database")


async def _clear_e2e_rows() -> None:
    if not _is_disposable_sqlite():
        return
    async with get_session_factory()() as session:
        await session.execute(delete(EmailDispatchModel))
        await session.execute(delete(EmailSenderSettingsModel))
        await session.execute(delete(DocumentModel))
        await session.execute(delete(AuditEventModel))
        await session.execute(delete(SessionModel))
        await session.execute(delete(MessageTemplateModel))
        await session.execute(delete(ClientFolderModel))
        await session.execute(delete(UserModel))
        await session.execute(delete(OwnerSlotModel))
        await session.commit()


@dataclass
class _SyntheticEmailSender:
    recipients: list[str] = field(default_factory=list)

    async def send(
        self,
        *,
        settings: EmailSenderSettings,
        message: OutboundEmail,
        credential: str | None,
    ) -> EmailDeliveryResult:
        assert settings.sender_email == "sender@example.com"
        assert credential == "synthetic-session-secret"
        self.recipients.append(message.recipient)
        return EmailDeliveryResult(EmailDeliveryStatus.SENT)


_SYNTHETIC_SENDER = _SyntheticEmailSender()


def _get_synthetic_send_use_case(
    session: DatabaseSession,
) -> SendEmailBatchUseCase:
    return SendEmailBatchUseCase(
        communications=SqlAlchemyCommunicationRepository(session),
        clients=SqlAlchemyClientFolderRepository(session),
        sender=_SYNTHETIC_SENDER,
        audit=RecordAuditEventUseCase(SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )


@pytest.fixture(autouse=True)
async def clear_e2e_rows() -> AsyncIterator[None]:
    """Isola o cenário e devolve o banco vazio para os testes seguintes."""
    await _clear_e2e_rows()
    yield
    await _clear_e2e_rows()


async def _owner_audit_actions(owner_id: uuid.UUID) -> set[str]:
    async with get_session_factory()() as session:
        events = (
            await session.scalars(
                select(AuditEventModel).where(AuditEventModel.actor_user_id == owner_id)
            )
        ).all()
    return {event.action for event in events}


async def test_owner_walks_the_core_mvp_flow(tmp_path: Path) -> None:
    _requires_disposable_sqlite()
    client = TestClient(app)
    email = f"e2e-{uuid.uuid4()}@deltaforce.internal"
    password = "correct-horse-battery-staple"

    # 1. Na primeira execução, o proprietário cria a única conta local.
    setup_status = client.get("/auth/setup")
    assert setup_status.status_code == 200
    assert setup_status.json() == {"requires_setup": True}

    setup = client.post(
        "/auth/setup",
        json={
            "email": email,
            "full_name": "Proprietário E2E",
            "password": password,
        },
    )
    assert setup.status_code == 201
    owner_id = uuid.UUID(setup.json()["user"]["id"])

    setup_status = client.get("/auth/setup")
    assert setup_status.status_code == 200
    assert setup_status.json() == {"requires_setup": False}

    # 2. Encerra a sessão inicial e entra novamente com a conta criada.
    initial_auth = {"Authorization": f"Bearer {setup.json()['session_token']}"}
    logout = client.post("/auth/logout", headers=initial_auth)
    assert logout.status_code == 204

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    assert login.json()["user"]["id"] == str(owner_id)
    auth = {"Authorization": f"Bearer {login.json()['session_token']}"}

    # 3. Cadastra cliente com a identificação aplicável (só campos disponíveis).
    folder_name = f"Cliente E2E {uuid.uuid4().hex[:8]}"
    created = client.post(
        "/clients",
        headers=auth,
        json={
            "display_name": folder_name,
            "email": "recipient@example.com",
            "profile_data": {"telefone": "(11) 90000-0000"},
        },
    )
    assert created.status_code == 201
    client_id = created.json()["id"]

    # 4. Anexa e classifica um documento (PDF).
    attached = client.post(
        f"/clients/{client_id}/documents",
        headers={
            **auth,
            "X-Delta-Document-Filename": "contrato.pdf",
            "X-Delta-Document-Title": "Contrato%20assinado",
            "X-Delta-Document-Category": "contrato",
        },
        content=PDF_BYTES,
    )
    assert attached.status_code == 201
    document_id = attached.json()["id"]

    # 5. Classifica o documento para a triagem de comunicação.
    classified = client.patch(
        f"/clients/{client_id}/documents/{document_id}/status",
        headers=auth,
        json={"status": "pending"},
    )
    assert classified.status_code == 200
    assert classified.json()["status"] == "pending"

    # 6. Consulta a lista e exporta o documento anexado.
    listing = client.get(
        f"/clients/{client_id}/documents", headers=auth, params={"limit": 20}
    )
    assert listing.status_code == 200
    assert any(
        item["id"] == document_id and item["status"] == "pending"
        for item in listing.json()["items"]
    )

    exported = client.get(
        f"/clients/{client_id}/documents/{document_id}/content", headers=auth
    )
    assert exported.status_code == 200
    assert exported.content.startswith(b"%PDF")

    # 7. Gera a ficha cadastral em PDF.
    profile = client.get(f"/clients/{client_id}/profile.pdf", headers=auth)
    assert profile.status_code == 200
    assert profile.headers["content-type"].startswith("application/pdf")
    assert profile.content.startswith(b"%PDF")
    assert "attachment" in profile.headers.get("content-disposition", "")

    # 8. Importa o acervo legado de uma pasta com o nome do cliente cadastrado.
    source = tmp_path / "acervo"
    (source / folder_name).mkdir(parents=True)
    (source / folder_name / "antigo.pdf").write_bytes(LEGACY_PDF_BYTES)

    preview = client.post(
        "/imports/legacy/preview", headers=auth, json={"source_path": str(source)}
    )
    assert preview.status_code == 200
    assert preview.json()["summary"]["matched"] >= 1

    imported = client.post(
        "/imports/legacy", headers=auth, json={"source_path": str(source)}
    )
    assert imported.status_code == 200
    assert imported.json()["summary"]["imported"] >= 1

    # 9. Cria um modelo estático e localiza o cliente na triagem documental.
    template = client.post(
        "/message-templates",
        headers=auth,
        json={
            "name": "Pendência documental E2E",
            "subject": "Documento pendente de {{nome}}",
            "body": "Olá, {{nome}}. Mensagem sintética para o teste ponta a ponta.",
        },
    )
    assert template.status_code == 201

    templates = client.get("/message-templates", headers=auth)
    assert templates.status_code == 200
    assert any(item["id"] == template.json()["id"] for item in templates.json())

    candidates = client.get(
        "/email-recipient-candidates",
        headers=auth,
        params={"status": "pending", "limit": 20},
    )
    assert candidates.status_code == 200
    matching_candidate = next(
        item for item in candidates.json()["items"] if item["client_id"] == client_id
    )
    assert matching_candidate == {
        "client_id": client_id,
        "display_name": folder_name,
        "document_status": "pending",
        "matching_documents": 1,
    }

    # 10. Configura dados públicos do remetente; a credencial não é persistida.
    sender_settings = client.put(
        "/email-sender-settings",
        headers=auth,
        json={
            "sender_name": "Escritório Sintético",
            "sender_email": "sender@example.com",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "security": "starttls",
            "username": "sender@example.com",
            "max_recipients": 20,
        },
    )
    assert sender_settings.status_code == 200
    sender_settings_read = client.get("/email-sender-settings", headers=auth)
    assert sender_settings_read.status_code == 200
    assert sender_settings_read.json()["username"] == "sender@example.com"

    # 11. Envia individualmente pelo adaptador falso e consulta o histórico.
    _SYNTHETIC_SENDER.recipients.clear()
    app.dependency_overrides[get_send_email_batch_use_case] = (
        _get_synthetic_send_use_case
    )
    try:
        sent = client.post(
            "/email-dispatches",
            headers=auth,
            json={
                "template_id": template.json()["id"],
                "client_ids": [client_id],
                "credential": "synthetic-session-secret",
                "confirm_repeat": False,
            },
        )
    finally:
        app.dependency_overrides.pop(get_send_email_batch_use_case, None)
    assert sent.status_code == 200
    assert sent.json()[0]["status"] == "sent"
    assert _SYNTHETIC_SENDER.recipients == ["recipient@example.com"]

    dispatch_history = client.get(
        "/email-dispatches", headers=auth, params={"limit": 20}
    )
    assert dispatch_history.status_code == 200
    assert dispatch_history.json()["items"][0]["client_id"] == client_id

    # 12. Consulta o histórico de auditoria pela própria API.
    audit = client.get("/audit/events", headers=auth, params={"limit": 50})
    assert audit.status_code == 200
    assert audit.json()["items"]

    # A trilha registra cada ação relevante do proprietário.
    actions = await _owner_audit_actions(owner_id)
    assert {
        "auth.owner_setup",
        "auth.login",
        "auth.logout",
        "client_folder.created",
        "document.stored",
        "document.status_updated",
        "document.exported",
        "client_folder.profile_exported",
        "message_template.created",
        "recipient_candidates.viewed",
        "email_sender_settings.updated",
        "email_sender_settings.viewed",
        "email_dispatch.batch_sent",
        "email_dispatch.history_viewed",
    } <= actions
