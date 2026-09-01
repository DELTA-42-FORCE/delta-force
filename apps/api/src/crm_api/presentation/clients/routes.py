"""Rotas HTTP autenticadas da pasta digital flexível de clientes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from crm_api.application.clients.create_client_folder import (
    CreateClientFolderUseCase,
)
from crm_api.application.clients.get_client_folder import GetClientFolderUseCase
from crm_api.application.clients.list_client_folders import (
    ListClientFoldersUseCase,
)
from crm_api.application.clients.update_client_folder import (
    UpdateClientFolderUseCase,
)
from crm_api.domain.clients.entities import ClientFolder, ClientFolderCursor
from crm_api.domain.clients.errors import ClientFolderNotFoundError
from crm_api.presentation.auth.dependencies import CurrentUser
from crm_api.presentation.clients.dependencies import (
    get_create_client_folder_use_case,
    get_get_client_folder_use_case,
    get_list_client_folders_use_case,
    get_update_client_folder_use_case,
)
from crm_api.presentation.clients.schemas import (
    ClientFolderCursorResponse,
    ClientFolderListResponse,
    ClientFolderResponse,
    CreateClientFolderRequest,
    UpdateClientFolderRequest,
)

router = APIRouter(prefix="/clients", tags=["clients"])

_NOT_FOUND_DETAIL = "client folder not found"


def _to_response(client: ClientFolder) -> ClientFolderResponse:
    return ClientFolderResponse(
        id=client.id,
        display_name=client.display_name,
        profile_data=dict(client.profile_data),
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


@router.post(
    "", response_model=ClientFolderResponse, status_code=status.HTTP_201_CREATED
)
async def create_client_folder(
    payload: CreateClientFolderRequest,
    current_user: CurrentUser,
    use_case: Annotated[
        CreateClientFolderUseCase, Depends(get_create_client_folder_use_case)
    ],
) -> ClientFolderResponse:
    try:
        client = await use_case.execute(
            actor_user_id=current_user.id,
            display_name=payload.display_name,
            profile_data=payload.profile_data,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from None
    return _to_response(client)


@router.get("", response_model=ClientFolderListResponse)
async def list_client_folders(
    current_user: CurrentUser,
    use_case: Annotated[
        ListClientFoldersUseCase, Depends(get_list_client_folders_use_case)
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    query: Annotated[str | None, Query()] = None,
    before_display_name: Annotated[str | None, Query()] = None,
    before_id: Annotated[UUID | None, Query()] = None,
) -> ClientFolderListResponse:
    if (before_display_name is None) != (before_id is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="before_display_name and before_id must be provided together",
        )
    try:
        cursor = (
            ClientFolderCursor(display_name=before_display_name, id=before_id)
            if before_display_name is not None and before_id is not None
            else None
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="client folder cursor is invalid",
        ) from None

    page = await use_case.execute(
        actor_user_id=current_user.id,
        limit=limit,
        before=cursor,
        query=query,
    )

    return ClientFolderListResponse(
        items=[_to_response(client) for client in page.items],
        limit=limit,
        next_cursor=(
            ClientFolderCursorResponse(
                display_name=page.next_cursor.display_name,
                id=page.next_cursor.id,
            )
            if page.next_cursor is not None
            else None
        ),
    )


@router.get("/{client_id}", response_model=ClientFolderResponse)
async def get_client_folder(
    client_id: UUID,
    current_user: CurrentUser,
    use_case: Annotated[
        GetClientFolderUseCase, Depends(get_get_client_folder_use_case)
    ],
) -> ClientFolderResponse:
    try:
        client = await use_case.execute(
            actor_user_id=current_user.id, client_id=client_id
        )
    except ClientFolderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL
        ) from None
    return _to_response(client)


@router.put("/{client_id}", response_model=ClientFolderResponse)
async def update_client_folder(
    client_id: UUID,
    payload: UpdateClientFolderRequest,
    current_user: CurrentUser,
    use_case: Annotated[
        UpdateClientFolderUseCase, Depends(get_update_client_folder_use_case)
    ],
) -> ClientFolderResponse:
    try:
        client = await use_case.execute(
            actor_user_id=current_user.id,
            client_id=client_id,
            display_name=payload.display_name,
            profile_data=payload.profile_data,
        )
    except ClientFolderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL
        ) from None
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from None
    return _to_response(client)
