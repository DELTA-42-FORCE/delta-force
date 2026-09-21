from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from crm_api.application.backups.manage_backups import (
    CreateBackupUseCase,
    GetBackupStatusUseCase,
    StageRestoreUseCase,
)
from crm_api.domain.auth.entities import User
from crm_api.infrastructure.backups.container import (
    BackupPasswordOrIntegrityError,
    InvalidBackupFormatError,
)
from crm_api.infrastructure.backups.media import BackupMediaError
from crm_api.infrastructure.backups.service import (
    BackupInsufficientSpaceError,
    BackupServiceError,
    BackupSourceIntegrityError,
    RestoreAlreadyPendingError,
    RestoreRequiresEmptyInstallationError,
)
from crm_api.presentation.auth.dependencies import (
    BearerToken,
    CurrentUser,
    get_current_user,
)
from crm_api.presentation.backups.dependencies import (
    get_backup_status_use_case,
    get_create_backup_use_case,
    get_stage_restore_use_case,
)
from crm_api.presentation.backups.schemas import (
    BackupCreationResponse,
    BackupStatusResponse,
    CreateBackupRequest,
    RestoreStagingResponse,
    StageRestoreRequest,
)
from crm_api.presentation.dependencies import DatabaseSession

router = APIRouter(prefix="/backups", tags=["backups"])


async def get_restore_actor(
    request: Request,
    session: DatabaseSession,
    session_token: BearerToken,
) -> User | None:
    if session_token is None:
        return None
    return await get_current_user(request, session, session_token)


RestoreActor = Annotated[User | None, Depends(get_restore_actor)]


@router.get("/status", response_model=BackupStatusResponse)
async def backup_status(
    current_user: CurrentUser,
    use_case: Annotated[GetBackupStatusUseCase, Depends(get_backup_status_use_case)],
) -> BackupStatusResponse:
    del current_user
    result = await use_case.execute()
    return BackupStatusResponse(
        last_successful_at=result.last_successful_at,
        reminder_due=result.reminder_due,
    )


@router.post(
    "", response_model=BackupCreationResponse, status_code=status.HTTP_201_CREATED
)
async def create_backup(
    payload: CreateBackupRequest,
    current_user: CurrentUser,
    use_case: Annotated[CreateBackupUseCase, Depends(get_create_backup_use_case)],
) -> BackupCreationResponse:
    try:
        result = await use_case.execute(
            actor_user_id=current_user.id,
            destination_directory=payload.destination_directory,
            passphrase=payload.passphrase.get_secret_value(),
        )
    except BackupMediaError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except BackupInsufficientSpaceError:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail="there is not enough space to create the backup",
        ) from None
    except (BackupSourceIntegrityError, OSError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="local data could not be captured consistently",
        ) from None
    except (BackupServiceError, InvalidBackupFormatError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return BackupCreationResponse(
        filename=result.filename,
        created_at=result.created_at,
        byte_size=result.byte_size,
        document_count=result.document_count,
    )


@router.post(
    "/restore",
    response_model=RestoreStagingResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def stage_restore(
    payload: StageRestoreRequest,
    request: Request,
    session: DatabaseSession,
    session_token: BearerToken,
    restore_actor: RestoreActor,
    use_case: Annotated[StageRestoreUseCase, Depends(get_stage_restore_use_case)],
) -> RestoreStagingResponse:
    if payload.replace_existing:
        if restore_actor is None:
            await get_current_user(request, session, session_token)
        if payload.confirmation != "SUBSTITUIR DADOS":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="reinforced restore confirmation is invalid",
            )
    try:
        result = await use_case.execute(
            source_file=payload.source_file,
            passphrase=payload.passphrase.get_secret_value(),
            replace_existing=payload.replace_existing,
        )
    except RestoreRequiresEmptyInstallationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="restore requires an empty installation",
        ) from None
    except RestoreAlreadyPendingError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="another restore is already pending",
        ) from None
    except BackupInsufficientSpaceError:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail="there is not enough space to validate the backup",
        ) from None
    except BackupMediaError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except (BackupPasswordOrIntegrityError, InvalidBackupFormatError):
        raise HTTPException(
            status_code=422,
            detail="backup password is wrong or the file is corrupted",
        ) from None
    except (BackupSourceIntegrityError, BackupServiceError, OSError, ValueError):
        raise HTTPException(
            status_code=422,
            detail="backup could not be validated",
        ) from None
    return RestoreStagingResponse(
        backup_created_at=result.created_at,
        document_count=result.document_count,
        requires_restart=result.requires_restart,
    )
