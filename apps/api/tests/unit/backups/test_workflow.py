"""Fluxo real sobre SQLite descartável, sem dados pessoais e sem HD real."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
import os
import sqlite3
import threading
from uuid import UUID

from alembic import command
from httpx import ASGITransport, AsyncClient
import pytest

import crm_api.application.backups.workflow as workflow_module
from crm_api.application.backups.workflow import DesktopBackupWorkflow
from crm_api.core.config import get_settings
from crm_api.desktop_server import (
    _alembic_config,
    _initialize_legacy_generation,
    _use_active_generation,
)
from crm_api.infrastructure.backups.activation import (
    _atomic_write_json,
    load_active_generation,
    resolve_active_generation,
)
from crm_api.infrastructure.backups.container import encrypt_payload
from crm_api.infrastructure.backups.snapshot import build_backup_payload
from crm_api.infrastructure.backups.restore import stage_backup_restore
from crm_api.infrastructure.backups.windows_volume import VolumeIdentity
from crm_api.infrastructure.database import get_engine, get_session_factory
from crm_api.main import create_app
from crm_api.presentation.backups.routes import _run
from .test_publisher import FakeInspector

OWNER_PASSWORD = "synthetic-owner-password"
PASSPHRASE = "synthetic-backup-password"


@pytest.fixture
async def desktop(tmp_path, monkeypatch):
    # Monkeypatch retains the caller's environment across generation switches.
    for key in ("DATABASE_URL", "DOCUMENTS_ROOT"):
        monkeypatch.setenv(key, os.environ.get(key, ""))
    await get_engine().dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    data = tmp_path / "data"
    paths = await asyncio.to_thread(
        load_active_generation, data, initialize_legacy=_initialize_legacy_generation
    )
    _use_active_generation(paths)
    workflow = DesktopBackupWorkflow(data)
    app = create_app()
    app.state.backup_workflow = workflow
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        setup = await client.post(
            "/auth/setup",
            json={
                "email": "synthetic@example.com",
                "full_name": "Proprietário fictício",
                "password": OWNER_PASSWORD,
            },
        )
        assert setup.status_code == 201, setup.text
        client.headers["Authorization"] = f"Bearer {setup.json()['session_token']}"
        try:
            yield client, workflow, UUID(setup.json()["user"]["id"])
        finally:
            await get_engine().dispose()
            get_engine.cache_clear()
            get_session_factory.cache_clear()
            get_settings.cache_clear()


def make_backup(workflow: DesktopBackupWorkflow) -> Path:
    active = resolve_active_generation(workflow.data_directory)
    target = workflow.data_directory.parent / "synthetic.dfcrmbak"
    with build_backup_payload(
        database_path=active.database_path,
        documents_root=active.documents_root,
        temporary_root=workflow.data_directory / "backup-staging",
    ) as payload:
        encrypt_payload(
            payload_path=payload.path,
            destination_path=target,
            passphrase=PASSPHRASE,
            app_version="0.1.0",
            created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            schema_revision=payload.schema_revision,
        )
    return target


async def preview(client, source):
    result = await client.post(
        "/backups/restore/preview",
        json={
            "source": str(source),
            "passphrase": PASSPHRASE,
        },
    )
    assert result.status_code == 200, result.text
    return result.json()


async def restore(client, token, **overrides):
    return await client.post(
        "/backups/restore",
        json={
            "preview_token": token,
            "passphrase": PASSPHRASE,
            "owner_password": OWNER_PASSWORD,
            "confirmation": "RESTAURAR",
            **overrides,
        },
    )


async def test_real_restore_replaces_clients_logs_activation_and_revokes_sessions(
    desktop,
):
    client, workflow, _ = desktop
    response = await client.post(
        "/clients", json={"display_name": "Cliente preservado"}
    )
    assert response.status_code == 201
    source = await asyncio.to_thread(make_backup, workflow)
    assert (
        await client.post("/clients", json={"display_name": "Cliente posterior"})
    ).status_code == 201
    reviewed = await preview(client, source)
    assert reviewed["current_records"]["clients"] == 2
    assert reviewed["candidate_records"]["clients"] == 1
    assert reviewed["replacement_required"] is True
    assert list((workflow.data_directory / "restore-staging").iterdir()) == []
    denied = await restore(
        client, reviewed["preview_token"], owner_password="incorrect"
    )
    assert denied.status_code == 403
    response = await restore(client, reviewed["preview_token"])
    assert response.status_code == 200, response.text
    assert response.json()["login_required"] is True
    assert (await client.get("/clients")).status_code == 401
    paths = resolve_active_generation(workflow.data_directory)
    assert paths.generation_id != "legacy"
    with sqlite3.connect(paths.database_path) as database:
        assert database.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
        assert (
            database.execute("SELECT COUNT(*) FROM client_folders").fetchone()[0] == 1
        )
        assert database.execute(
            "SELECT actor_kind, actor_user_id, context FROM audit_events "
            "WHERE action = 'backup.restore_applied'"
        ).fetchone() == ("anonymous", None, "{}")
    login = await client.post(
        "/auth/login",
        json={
            "email": "synthetic@example.com",
            "password": OWNER_PASSWORD,
        },
    )
    assert login.status_code == 200, login.text
    client.headers["Authorization"] = f"Bearer {login.json()['session_token']}"
    assert [
        row["display_name"] for row in (await client.get("/clients")).json()["items"]
    ] == ["Cliente preservado"]


@pytest.mark.parametrize("change", ["data", "source", "expired", "owner"])
async def test_preview_cannot_be_reused_after_change(desktop, change):
    client, workflow, owner = desktop
    source = await asyncio.to_thread(make_backup, workflow)
    reviewed = await preview(client, source)
    token = reviewed["preview_token"]
    if change == "data":
        await client.post("/clients", json={"display_name": "Cliente posterior"})
    elif change == "source":
        with source.open("ab") as stream:
            stream.write(b"altered")
    elif change == "expired":
        workflow._previews[token] = replace(workflow._previews[token], expires_at=0)
    else:
        workflow._previews[token] = replace(
            workflow._previews[token], owner_id=UUID(int=1)
        )
    response = await restore(client, token)
    assert response.status_code == 409, response.text
    assert resolve_active_generation(workflow.data_directory).generation_id == "legacy"
    assert workflow.recovery_required is False


async def test_backup_auth_validation_and_failure_do_not_echo_secrets(
    desktop, monkeypatch
):
    client, workflow, _ = desktop
    authorization = client.headers.pop("Authorization")
    assert (await client.get("/backups/status")).status_code == 401
    client.headers["Authorization"] = authorization
    sensitive = "C:\\private\\synthetic.dfcrmbak"
    response = await client.post(
        "/backups/restore/preview", json={"source": sensitive, "passphrase": "short"}
    )
    assert response.json() == {"detail": "backup_invalid_input"}
    assert sensitive not in response.text and "short" not in response.text

    def failed(*args):
        raise OSError("private path and passphrase")

    monkeypatch.setattr(workflow, "preview_restore", failed)
    response = await client.post(
        "/backups/restore/preview", json={"source": sensitive, "passphrase": PASSPHRASE}
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "backup_operation_failed"}
    with sqlite3.connect(
        resolve_active_generation(workflow.data_directory).database_path
    ) as database:
        row = database.execute(
            "SELECT context, result FROM audit_events "
            "WHERE action='backup.restore_reviewed'"
        ).fetchone()
        assert row == ("{}", "failure")


async def test_reminder_respects_chosen_interval_and_has_no_default(desktop):
    client, workflow, _ = desktop
    assert (await client.get("/backups/status")).json()["interval_days"] is None
    response = await client.put("/backups/reminder", json={"interval_days": 14})
    assert response.json()["reminder_due"] is True
    _atomic_write_json(
        workflow._preferences_path,
        {
            "interval_days": 14,
            "last_backup_at": (datetime.now(UTC) - timedelta(days=13)).isoformat(),
        },
    )
    assert (await client.get("/backups/status")).json()["reminder_due"] is False
    assert (await client.put("/backups/reminder", json={"interval_days": None})).json()[
        "reminder_due"
    ] is False
    assert (
        await client.put("/backups/reminder", json={"interval_days": True})
    ).status_code == 422


async def test_cancelled_request_waits_for_worker():
    started, release, finished = threading.Event(), threading.Event(), threading.Event()

    def operation():
        started.set()
        release.wait(timeout=5)
        finished.set()

    task = asyncio.create_task(_run(operation))
    assert await asyncio.to_thread(started.wait, 5)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()


async def test_completed_backup_survives_reminder_write_failure(desktop, monkeypatch):
    _, workflow, _ = desktop
    monkeypatch.setattr(
        workflow,
        "estimate",
        lambda _: {
            "required_bytes": 1,
            "available_bytes": 2,
            "local_required_bytes": 1,
            "local_available_bytes": 2,
        },
    )

    class Inspector:
        def identify_volume(self, path):
            return type("Volume", (), {"volume_id": "synthetic"})()

    monkeypatch.setattr(workflow_module, "WindowsVolumeInspector", Inspector)
    published = []
    monkeypatch.setattr(
        workflow_module, "publish_backup", lambda **kwargs: published.append(True)
    )

    def failed(*args):
        raise OSError("synthetic preference failure")

    monkeypatch.setattr(workflow_module, "_atomic_write_json", failed)
    result = workflow.create_backup(str(workflow.data_directory.parent), PASSPHRASE)
    assert published == [True]
    assert result == {"completed": True, "reminder_updated": False}


async def test_audit_migration_round_trip_and_refuses_loss(desktop):
    _, workflow, _ = desktop
    paths = resolve_active_generation(workflow.data_directory)
    await get_engine().dispose()
    config = _alembic_config(paths.database_path)
    await asyncio.to_thread(command.downgrade, config, "20260920_0016")
    await asyncio.to_thread(command.upgrade, config, "head")
    with sqlite3.connect(paths.database_path) as database:
        database.execute(
            "INSERT INTO audit_events "
            "(id, occurred_at, actor_kind, action, resource_type, result, context) "
            "VALUES (?, ?, 'anonymous', 'backup.created', 'backup', 'success', '{}')",
            (UUID(int=2).hex, datetime.now(UTC).replace(tzinfo=None).isoformat(" ")),
        )
    with pytest.raises(RuntimeError, match="preserved"):
        await asyncio.to_thread(command.downgrade, config, "20260920_0016")
    with sqlite3.connect(paths.database_path) as database:
        assert (
            database.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "20260930_0017"
        )


async def test_real_creation_estimates_publishes_and_updates_sanitized_audit(
    desktop, monkeypatch
):
    client, workflow, _ = desktop
    external = workflow.data_directory.parent / "simulated-external"
    external.mkdir()

    class Inspector(FakeInspector):
        def identify_volume(self, path):
            return VolumeIdentity(
                canonical_directory=path,
                volume_id="system-volume",
                filesystem="NTFS",
                is_removable=False,
                is_usb=False,
            )

    monkeypatch.setattr(
        workflow_module, "WindowsVolumeInspector", lambda: Inspector(external)
    )
    response = await client.post(
        "/backups/estimate", json={"destination": str(external)}
    )
    assert response.status_code == 200, response.text
    assert response.json()["required_bytes"] > 0
    response = await client.post(
        "/backups", json={"destination": str(external), "passphrase": PASSPHRASE}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"completed": True, "reminder_updated": True}
    backups = list(external.glob("*.dfcrmbak"))
    assert len(backups) == 1
    with stage_backup_restore(
        source_path=backups[0],
        passphrase=PASSPHRASE,
        temporary_root=workflow.data_directory / "restore-staging",
    ) as staged:
        assert staged.database_path.is_file()
    assert (await client.get("/backups/status")).json()["last_backup_at"] is not None
    with sqlite3.connect(
        resolve_active_generation(workflow.data_directory).database_path
    ) as database:
        assert database.execute(
            "SELECT context, result FROM audit_events WHERE action='backup.created'"
        ).fetchone() == ("{}", "success")


async def test_interrupted_activation_blocks_other_requests_until_restart(
    desktop, monkeypatch
):
    client, workflow, _ = desktop
    source = await asyncio.to_thread(make_backup, workflow)
    reviewed = await preview(client, source)

    def failed(**kwargs):
        raise OSError("synthetic interrupted activation")

    monkeypatch.setattr(workflow_module, "activate_restore_candidate", failed)
    response = await restore(client, reviewed["preview_token"])
    assert response.status_code == 503
    assert workflow.recovery_required is True
    assert (await client.get("/clients")).json() == {
        "detail": "backup_restart_required"
    }


@pytest.mark.parametrize(
    "value", ["relative.dfcrmbak", "\\\\server\\share\\backup.dfcrmbak"]
)
def test_source_selection_rejects_relative_and_network_paths(value):
    with pytest.raises(ValueError):
        DesktopBackupWorkflow._absolute_path(value)
