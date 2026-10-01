"""Rotas desktop autenticadas; respostas e auditoria não expõem caminhos/segredos."""

import asyncio
import sqlite3
import unicodedata
from typing import Annotated
from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from alembic.util.exc import CommandError

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.backups.workflow import (
    DesktopBackupWorkflow,
    StaleRestorePreviewError,
)
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.auth.entities import User
from crm_api.infrastructure.audit.repositories import SqlAlchemyAuditEventRepository
from crm_api.infrastructure.auth.passwords import BcryptPasswordHasher
from crm_api.infrastructure.backups.container import BackupContainerError
from crm_api.infrastructure.backups.publisher import BackupPublicationError
from crm_api.infrastructure.backups.snapshot import BackupSnapshotError
from crm_api.infrastructure.backups.restore import (
    InvalidRestoreBackupError,
    InsufficientRestoreSpaceError,
)
from crm_api.infrastructure.backups.activation import RestoreActivationError
from crm_api.infrastructure.database import get_engine, get_session_factory
from crm_api.presentation.auth.dependencies import CurrentUser
from crm_api.presentation.dependencies import DatabaseSession

router = APIRouter(prefix="/backups", tags=["backups"])


def get_workflow(request: Request) -> DesktopBackupWorkflow:
    workflow = getattr(request.app.state, "backup_workflow", None)
    if not isinstance(workflow, DesktopBackupWorkflow):
        raise HTTPException(404, "backup_requires_desktop")
    if workflow.recovery_required:
        raise HTTPException(503, "backup_restart_required")
    return workflow


Workflow = Annotated[DesktopBackupWorkflow, Depends(get_workflow)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("passphrase", check_fields=False)
    @classmethod
    def validate_passphrase(cls, value: SecretStr) -> SecretStr:
        size = len(
            unicodedata.normalize("NFC", value.get_secret_value()).encode("utf-8")
        )
        if not 12 <= size <= 1024:
            raise ValueError("invalid backup passphrase length")
        return value


class DestinationInput(Input):
    destination: str = Field(min_length=1, max_length=32767)


class BackupInput(DestinationInput):
    passphrase: SecretStr = Field(max_length=1024)


class PreviewInput(Input):
    source: str = Field(min_length=1, max_length=32767)
    passphrase: SecretStr = Field(max_length=1024)


class RestoreInput(Input):
    preview_token: str = Field(pattern=r"^[0-9a-f]{32}$")
    passphrase: SecretStr = Field(max_length=1024)
    owner_password: SecretStr = Field(min_length=1, max_length=72)
    confirmation: str = Field(max_length=32)

    @field_validator("owner_password")
    @classmethod
    def owner_password_fits_bcrypt(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) > 72:
            raise ValueError("invalid owner password length")
        return value


class ReminderInput(Input):
    interval_days: int | None = Field(default=None, ge=1, le=365, strict=True)


async def _record(
    session: AsyncSession,
    user: User,
    action: AuditAction,
    result: AuditResult = AuditResult.SUCCESS,
) -> None:
    await RecordAuditEventUseCase(SqlAlchemyAuditEventRepository(session)).execute(
        actor_kind=AuditActorKind.AUTHENTICATED,
        actor_user_id=user.id,
        action=action,
        resource_type=AuditResourceType.BACKUP,
        resource_id=None,
        result=result,
    )
    await session.commit()


T = TypeVar("T")


async def _run(operation: Callable[..., T], *args: object) -> T:
    task = asyncio.create_task(asyncio.to_thread(operation, *args))
    try:
        cancelled = False
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                # Nem cancelamentos repetidos liberam o banco durante a troca.
                cancelled = True
        result = task.result()
        if cancelled:
            raise asyncio.CancelledError
        return result
    except StaleRestorePreviewError:
        raise HTTPException(409, "backup_preview_expired") from None
    except InsufficientRestoreSpaceError:
        raise HTTPException(422, "backup_insufficient_space") from None
    except RestoreActivationError:
        raise HTTPException(503, "backup_restart_required") from None
    except (
        BackupContainerError,
        BackupSnapshotError,
        BackupPublicationError,
        InvalidRestoreBackupError,
        OSError,
        ValueError,
        sqlite3.Error,
        SQLAlchemyError,
        RuntimeError,
        CommandError,
    ):
        raise HTTPException(422, "backup_operation_failed") from None


@router.get("/status")
async def backup_status(workflow: Workflow, user: CurrentUser) -> dict[str, object]:
    return await _run(workflow.status)


@router.put("/reminder")
async def configure_reminder(
    body: ReminderInput, workflow: Workflow, user: CurrentUser, session: DatabaseSession
):
    result = await _run(workflow.configure_reminder, body.interval_days)
    await _record(session, user, AuditAction.BACKUP_REMINDER_UPDATED)
    return result


@router.post("/estimate")
async def estimate_backup(
    body: DestinationInput, workflow: Workflow, user: CurrentUser
):
    return await _run(workflow.estimate, body.destination)


@router.post("")
async def create_backup(
    body: BackupInput, workflow: Workflow, user: CurrentUser, session: DatabaseSession
):
    try:
        result = await _run(
            workflow.create_backup, body.destination, body.passphrase.get_secret_value()
        )
    except HTTPException:
        await _record(session, user, AuditAction.BACKUP_CREATED, AuditResult.FAILURE)
        raise
    await _record(session, user, AuditAction.BACKUP_CREATED)
    return result


@router.post("/restore/preview")
async def preview_restore(
    body: PreviewInput, workflow: Workflow, user: CurrentUser, session: DatabaseSession
):
    try:
        result = await _run(
            workflow.preview_restore,
            body.source,
            body.passphrase.get_secret_value(),
            user.id,
        )
    except HTTPException:
        await _record(
            session, user, AuditAction.BACKUP_RESTORE_REVIEWED, AuditResult.FAILURE
        )
        raise
    await _record(session, user, AuditAction.BACKUP_RESTORE_REVIEWED)
    return result


@router.post("/restore")
async def apply_restore(
    body: RestoreInput, workflow: Workflow, user: CurrentUser, session: DatabaseSession
):
    verified = await asyncio.to_thread(
        BcryptPasswordHasher().verify,
        password=body.owner_password.get_secret_value(),
        password_hash=user.password_hash,
    )
    if body.confirmation != "RESTAURAR" or not verified:
        await _record(
            session, user, AuditAction.BACKUP_RESTORE_AUTHORIZED, AuditResult.DENIED
        )
        raise HTTPException(403, "backup_confirmation_required")
    await _record(session, user, AuditAction.BACKUP_RESTORE_AUTHORIZED)
    await session.close()
    await get_engine().dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    await _run(
        workflow.apply_restore,
        body.preview_token,
        body.passphrase.get_secret_value(),
        user.id,
    )
    return {"completed": True, "login_required": True}
