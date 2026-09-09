"""E2E parcial do MVP (#27): encadeia pela API HTTP os fluxos já entregues.

Cobre login, cadastro de cliente, anexo/consulta/exportação de documento, ficha
cadastral em PDF, importação do acervo legado e a trilha de auditoria — validando
o critério de aceite ponta a ponta do #27 nas partes disponíveis. O passo de mala
direta (selecionar pendência e enviar e-mail em lote) depende de #23/#24/#25 e
fica explicitamente pendente em ``test_batch_email_step_is_pending``.
"""

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from crm_api.infrastructure.audit.models import AuditEventModel
from crm_api.infrastructure.auth.models import SessionModel, UserModel
from crm_api.infrastructure.auth.passwords import BcryptPasswordHasher
from crm_api.infrastructure.clients.models import ClientFolderModel
from crm_api.infrastructure.database import get_engine, get_session_factory
from crm_api.infrastructure.documents.models import DocumentModel
from crm_api.main import app

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


@pytest.fixture(autouse=True)
async def clear_e2e_rows() -> AsyncIterator[None]:
    """Devolve o banco compartilhado vazio para os round-trips de migration da suíte."""
    yield
    if not _is_disposable_sqlite():
        return
    async with get_session_factory()() as session:
        await session.execute(delete(DocumentModel))
        await session.execute(delete(AuditEventModel))
        await session.execute(delete(SessionModel))
        await session.execute(delete(ClientFolderModel))
        await session.execute(delete(UserModel))
        await session.commit()


async def _seed_active_owner() -> tuple[str, str, uuid.UUID]:
    email = f"e2e-{uuid.uuid4()}@deltaforce.internal"
    password = "correct-horse-battery-staple"
    user_id = uuid.uuid4()
    async with get_session_factory()() as session:
        session.add(
            UserModel(
                id=user_id,
                email=email,
                full_name="Proprietário E2E",
                password_hash=BcryptPasswordHasher().hash(password),
                is_active=True,
            )
        )
        await session.commit()
    return email, password, user_id


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
    email, password, owner_id = await _seed_active_owner()
    client = TestClient(app)

    # 1. Usuário autorizado entra com sua conta.
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    auth = {"Authorization": f"Bearer {login.json()['session_token']}"}

    # 2. Cadastra cliente com a identificação aplicável (só campos disponíveis).
    folder_name = f"Cliente E2E {uuid.uuid4().hex[:8]}"
    created = client.post(
        "/clients",
        headers=auth,
        json={
            "display_name": folder_name,
            "profile_data": {"telefone": "(11) 90000-0000"},
        },
    )
    assert created.status_code == 201
    client_id = created.json()["id"]

    # 3. Anexa e classifica um documento (PDF).
    attached = client.post(
        f"/clients/{client_id}/documents",
        headers=auth,
        files={"file": ("contrato.pdf", PDF_BYTES, "application/pdf")},
        data={"title": "Contrato assinado", "category": "contrato"},
    )
    assert attached.status_code == 201
    document_id = attached.json()["id"]

    # 4. Consulta a lista e exporta o documento anexado.
    listing = client.get(
        f"/clients/{client_id}/documents", headers=auth, params={"limit": 20}
    )
    assert listing.status_code == 200
    assert any(item["id"] == document_id for item in listing.json()["items"])

    exported = client.get(
        f"/clients/{client_id}/documents/{document_id}/content", headers=auth
    )
    assert exported.status_code == 200
    assert exported.content.startswith(b"%PDF")

    # 5. Gera a ficha cadastral em PDF.
    profile = client.get(f"/clients/{client_id}/profile.pdf", headers=auth)
    assert profile.status_code == 200
    assert profile.headers["content-type"].startswith("application/pdf")
    assert profile.content.startswith(b"%PDF")
    assert "attachment" in profile.headers.get("content-disposition", "")

    # 6. Importa o acervo legado de uma pasta com o nome do cliente cadastrado.
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

    # 7. Consulta o histórico pela própria API.
    audit = client.get("/audit/events", headers=auth, params={"limit": 50})
    assert audit.status_code == 200
    assert audit.json()["items"]

    # A trilha registra cada ação relevante do proprietário.
    actions = await _owner_audit_actions(owner_id)
    assert {
        "auth.login",
        "client_folder.created",
        "document.stored",
        "document.exported",
        "client_folder.profile_exported",
    } <= actions


async def test_batch_email_step_is_pending() -> None:
    # O passo "selecionar pendência e enviar e-mail em lote" do #27 depende do
    # status de documentos (#23), dos modelos/seleção de destinatários (#24) e do
    # envio (#25), ainda não integrados. Fica pendente para manter o critério
    # visível na suíte sem falhar a validação parcial.
    pytest.skip("mala direta pendente: depende de #23/#24/#25")
