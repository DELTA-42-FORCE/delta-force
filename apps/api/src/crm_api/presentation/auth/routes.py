"""Rotas HTTP de autenticação: login, sessão atual e logout."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from crm_api.application.auth.authenticate_user import (
    AuthenticateUserUseCase,
    AuthenticationResult,
)
from crm_api.application.auth.logout import LogoutUseCase
from crm_api.application.auth.setup_owner import (
    GetSetupStatusUseCase,
    SetupOwnerUseCase,
)
from crm_api.domain.auth.errors import (
    InactiveUserError,
    InvalidCredentialsError,
    SetupAlreadyCompletedError,
)
from crm_api.presentation.auth.dependencies import (
    BearerToken,
    CurrentUser,
    get_authenticate_user_use_case,
    get_logout_use_case,
    get_setup_owner_use_case,
    get_setup_status_use_case,
)
from crm_api.presentation.auth.schemas import (
    AuthenticatedUser,
    LoginRequest,
    LoginResponse,
    SetupOwnerRequest,
    SetupStatusResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_INVALID_CREDENTIALS_DETAIL = "invalid email or password"


def _to_login_response(result: AuthenticationResult) -> LoginResponse:
    return LoginResponse(
        session_token=result.session_token,
        expires_at=result.session.expires_at,
        user=AuthenticatedUser(
            id=result.user.id,
            email=result.user.email,
            full_name=result.user.full_name,
        ),
    )


@router.get("/setup", response_model=SetupStatusResponse)
async def setup_status(
    use_case: Annotated[GetSetupStatusUseCase, Depends(get_setup_status_use_case)],
) -> SetupStatusResponse:
    return SetupStatusResponse(requires_setup=await use_case.execute())


@router.post(
    "/setup", response_model=LoginResponse, status_code=status.HTTP_201_CREATED
)
async def setup_owner(
    payload: SetupOwnerRequest,
    use_case: Annotated[SetupOwnerUseCase, Depends(get_setup_owner_use_case)],
) -> LoginResponse:
    try:
        result = await use_case.execute(
            email=payload.email,
            full_name=payload.full_name,
            password=payload.password,
        )
    except SetupAlreadyCompletedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="initial setup has already been completed",
        ) from None
    return _to_login_response(result)


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    use_case: Annotated[
        AuthenticateUserUseCase, Depends(get_authenticate_user_use_case)
    ],
) -> LoginResponse:
    try:
        result = await use_case.execute(email=payload.email, password=payload.password)
    except (InvalidCredentialsError, InactiveUserError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDENTIALS_DETAIL,
        ) from None

    return _to_login_response(result)


@router.get("/me", response_model=AuthenticatedUser)
async def read_current_user(current_user: CurrentUser) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: CurrentUser,
    session_token: BearerToken,
    use_case: Annotated[LogoutUseCase, Depends(get_logout_use_case)],
) -> None:
    del current_user  # exige sessão válida antes de permitir o logout
    await use_case.execute(session_token=session_token)
