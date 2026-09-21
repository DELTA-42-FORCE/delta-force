from datetime import UTC, datetime
from uuid import UUID

import pytest

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.backups.manage_backups import CreateBackupUseCase
from crm_api.domain.backups.entities import BackupCreationResult


class RecordingBackupService:
    def __init__(self) -> None:
        self.discarded: list[tuple[str, str]] = []

    def create_backup(
        self, *, destination_directory: str, passphrase: str
    ) -> BackupCreationResult:
        return BackupCreationResult(
            filename="delta-force-crm-20260920T220000Z-1234abcd.dfcrmbak",
            created_at=datetime(2026, 9, 20, 22, tzinfo=UTC),
            byte_size=42,
            document_count=1,
        )

    def discard_backup(self, *, destination_directory: str, filename: str) -> None:
        self.discarded.append((destination_directory, filename))


class ControlledAuditRepository:
    def __init__(self, *, fail: bool) -> None:
        self.fail = fail

    async def append(self, event: object) -> None:
        if self.fail:
            raise RuntimeError("synthetic audit failure")


class ControlledTransaction:
    def __init__(self, *, fail_commit: bool) -> None:
        self.fail_commit = fail_commit
        self.commit_calls = 0
        self.rollback_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1
        if self.fail_commit:
            raise RuntimeError("synthetic commit failure")

    async def rollback(self) -> None:
        self.rollback_calls += 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_point", ["audit", "commit"])
async def test_audit_failure_discards_published_backup(
    failure_point: str,
) -> None:
    service = RecordingBackupService()
    transaction = ControlledTransaction(fail_commit=failure_point == "commit")
    audit_repository = ControlledAuditRepository(fail=failure_point == "audit")
    use_case = CreateBackupUseCase(
        service=service,  # type: ignore[arg-type]
        audit=RecordAuditEventUseCase(audit_repository),  # type: ignore[arg-type]
        transaction=transaction,
    )

    with pytest.raises(RuntimeError, match=f"synthetic {failure_point} failure"):
        await use_case.execute(
            actor_user_id=UUID("00000000-0000-0000-0000-000000000044"),
            destination_directory=r"E:\Backups",
            passphrase="senha sintetica forte",
        )

    assert transaction.rollback_calls == 1
    assert service.discarded == [
        (
            r"E:\Backups",
            "delta-force-crm-20260920T220000Z-1234abcd.dfcrmbak",
        )
    ]
