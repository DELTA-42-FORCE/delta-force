"""Rotas HTTP de autenticação: login, sessão atual e logout."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from crm_api.application.auth.authenticate_user import AuthenticateUserUseCase
from crm_api.application.auth.logout import LogoutUseCase
from crm_api.domain.auth.errors import InactiveUserError, InvalidCredentialsError
from crm_api.presentation.auth.dependencies import (
    BearerToken,
    CurrentUser,
    get_authenticate_user_use_case,
    get_logout_use_case,
)
from crm_api.presentation.auth.schemas import (
    AuthenticatedUser,
    LoginRequest,
    LoginResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_INVALID_CREDENTIALS_DETAIL = "invalid email or password"


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

    return LoginResponse(
        session_token=result.session.token,
        expires_at=result.session.expires_at,
        user=AuthenticatedUser(
            id=result.user.id,
            email=result.user.email,
            full_name=result.user.full_name,
        ),
    )


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
