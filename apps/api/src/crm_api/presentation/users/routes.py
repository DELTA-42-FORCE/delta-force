"""Rotas HTTP de gestão de usuários autorizados (somente administrador)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from crm_api.application.users.create_user import CreateUserUseCase
from crm_api.application.users.list_users import ListUsersUseCase
from crm_api.application.users.set_user_active import SetUserActiveUseCase
from crm_api.application.users.update_user import UpdateUserUseCase
from crm_api.domain.auth.entities import User
from crm_api.domain.users.errors import (
    CannotDeactivateSelfError,
    EmailAlreadyRegisteredError,
    UserNotFoundError,
)
from crm_api.presentation.users.dependencies import (
    AdminUser,
    get_create_user_use_case,
    get_list_users_use_case,
    get_set_user_active_use_case,
    get_update_user_use_case,
)
from crm_api.presentation.users.schemas import (
    CreateUserRequest,
    UpdateUserRequest,
    UserResponse,
)

router = APIRouter(prefix="/users", tags=["users"])


def _to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_admin=user.is_admin,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserRequest,
    _admin: AdminUser,
    use_case: Annotated[CreateUserUseCase, Depends(get_create_user_use_case)],
) -> UserResponse:
    try:
        user = await use_case.execute(
            email=payload.email,
            full_name=payload.full_name,
            password=payload.password,
            is_admin=payload.is_admin,
        )
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already registered",
        ) from None

    return _to_response(user)


@router.get("", response_model=list[UserResponse])
async def list_users(
    _admin: AdminUser,
    use_case: Annotated[ListUsersUseCase, Depends(get_list_users_use_case)],
) -> list[UserResponse]:
    users = await use_case.execute()
    return [_to_response(user) for user in users]


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    payload: UpdateUserRequest,
    _admin: AdminUser,
    use_case: Annotated[UpdateUserUseCase, Depends(get_update_user_use_case)],
) -> UserResponse:
    try:
        user = await use_case.execute(
            user_id=user_id,
            full_name=payload.full_name,
            is_admin=payload.is_admin,
        )
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user not found"
        ) from None

    return _to_response(user)


async def _set_active(
    *,
    user_id: UUID,
    is_active: bool,
    admin: User,
    use_case: SetUserActiveUseCase,
) -> UserResponse:
    try:
        user = await use_case.execute(
            acting_admin_id=admin.id, user_id=user_id, is_active=is_active
        )
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user not found"
        ) from None
    except CannotDeactivateSelfError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="an administrator cannot deactivate their own account",
        ) from None

    return _to_response(user)


@router.post("/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: UUID,
    admin: AdminUser,
    use_case: Annotated[SetUserActiveUseCase, Depends(get_set_user_active_use_case)],
) -> UserResponse:
    return await _set_active(
        user_id=user_id, is_active=True, admin=admin, use_case=use_case
    )


@router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: UUID,
    admin: AdminUser,
    use_case: Annotated[SetUserActiveUseCase, Depends(get_set_user_active_use_case)],
) -> UserResponse:
    return await _set_active(
        user_id=user_id, is_active=False, admin=admin, use_case=use_case
    )
