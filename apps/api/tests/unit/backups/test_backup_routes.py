from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from fastapi.testclient import TestClient

from crm_api.application.backups.manage_backups import BackupStatus
from crm_api.domain.auth.entities import User
from crm_api.domain.backups.entities import (
    BackupCreationResult,
    RestoreStagingResult,
)
from crm_api.infrastructure.backups.container import BackupPasswordOrIntegrityError
from crm_api.main import app
from crm_api.presentation.auth.dependencies import get_current_user
from crm_api.presentation.backups.dependencies import (
    get_backup_status_use_case,
    get_create_backup_use_case,
    get_stage_restore_use_case,
)
from crm_api.presentation.backups.routes import get_restore_actor

_OWNER = User(
    id=UUID("00000000-0000-0000-0000-000000000044"),
    email="owner-backup@example.com",
    full_name="Proprietário Sintético",
    password_hash="not-returned",
    is_active=True,
)


@dataclass
class FakeCreateBackup:
    passphrases: list[str] = field(default_factory=list)

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        destination_directory: str,
        passphrase: str,
    ) -> BackupCreationResult:
        assert actor_user_id == _OWNER.id
        assert destination_directory == "E:\\Backups"
        self.passphrases.append(passphrase)
        return BackupCreationResult(
            filename="delta-force-crm-synthetic.dfcrmbak",
            created_at=datetime(2026, 9, 19, 20, tzinfo=UTC),
            byte_size=1234,
            document_count=2,
        )


class FakeBackupStatus:
    async def execute(self) -> BackupStatus:
        return BackupStatus(last_successful_at=None, reminder_due=True)


class FakeRestore:
    async def execute(
        self, *, source_file: str, passphrase: str, replace_existing: bool = False
    ) -> RestoreStagingResult:
        assert source_file == "E:\\Backups\\synthetic.dfcrmbak"
        assert passphrase == "senha sintetica forte"
        assert replace_existing is False
        return RestoreStagingResult(created_at="2026-09-19T20:00:00Z", document_count=2)


class RejectingRestore:
    async def execute(
        self, *, source_file: str, passphrase: str, replace_existing: bool = False
    ) -> RestoreStagingResult:
        del source_file, passphrase, replace_existing
        raise BackupPasswordOrIntegrityError


class ReplacingRestore:
    async def execute(
        self, *, source_file: str, passphrase: str, replace_existing: bool = False
    ) -> RestoreStagingResult:
        del source_file, passphrase
        assert replace_existing is True
        return RestoreStagingResult(created_at="2026-09-19T20:00:00Z", document_count=2)


def _authenticated_client() -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: _OWNER
    return TestClient(app)


def _deny_authentication() -> None:
    raise HTTPException(status_code=401, detail="invalid or expired session")


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_authenticated_owner_creates_backup_without_returning_passphrase() -> None:
    use_case = FakeCreateBackup()
    app.dependency_overrides[get_create_backup_use_case] = lambda: use_case

    response = _authenticated_client().post(
        "/backups",
        json={
            "destination_directory": "E:\\Backups",
            "passphrase": "senha sintetica forte",
        },
    )

    assert response.status_code == 201
    assert response.json()["document_count"] == 2
    assert "passphrase" not in response.text
    assert use_case.passphrases == ["senha sintetica forte"]


def test_backup_status_requires_authentication() -> None:
    app.dependency_overrides[get_backup_status_use_case] = lambda: FakeBackupStatus()
    app.dependency_overrides[get_current_user] = _deny_authentication

    response = TestClient(app).get("/backups/status")

    assert response.status_code == 401


def test_restore_can_be_staged_before_owner_setup() -> None:
    app.dependency_overrides[get_stage_restore_use_case] = lambda: FakeRestore()

    response = TestClient(app).post(
        "/backups/restore",
        json={
            "source_file": "E:\\Backups\\synthetic.dfcrmbak",
            "passphrase": "senha sintetica forte",
        },
    )

    assert response.status_code == 202
    assert response.json() == {
        "backup_created_at": "2026-09-19T20:00:00Z",
        "document_count": 2,
        "requires_restart": True,
    }


def test_restore_hides_whether_password_or_content_failed() -> None:
    app.dependency_overrides[get_stage_restore_use_case] = lambda: RejectingRestore()

    response = TestClient(app).post(
        "/backups/restore",
        json={
            "source_file": "E:\\Backups\\synthetic.dfcrmbak",
            "passphrase": "senha sintetica errada",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "backup password is wrong or the file is corrupted"
    )


def test_replacement_requires_owner_and_reinforced_confirmation() -> None:
    app.dependency_overrides[get_stage_restore_use_case] = lambda: ReplacingRestore()
    app.dependency_overrides[get_restore_actor] = lambda: _OWNER

    missing_confirmation = TestClient(app).post(
        "/backups/restore",
        json={
            "source_file": "E:\\Backups\\synthetic.dfcrmbak",
            "passphrase": "senha sintetica forte",
            "replace_existing": True,
        },
    )
    accepted = TestClient(app).post(
        "/backups/restore",
        json={
            "source_file": "E:\\Backups\\synthetic.dfcrmbak",
            "passphrase": "senha sintetica forte",
            "replace_existing": True,
            "confirmation": "SUBSTITUIR DADOS",
        },
    )

    assert missing_confirmation.status_code == 422
    assert accepted.status_code == 202
