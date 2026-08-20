"""Dependências FastAPI que fiam os casos de uso de autenticação aos adaptadores."""

from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from crm_api.application.auth.authenticate_user import AuthenticateUserUseCase
from crm_api.application.auth.get_current_user import GetCurrentUserUseCase
from crm_api.application.auth.logout import LogoutUseCase
from crm_api.application.auth.setup_owner import (
    GetSetupStatusUseCase,
    SetupOwnerUseCase,
)
from crm_api.core.config import get_settings
from crm_api.domain.auth.entities import User
from crm_api.domain.auth.errors import InactiveUserError, InvalidSessionError
from crm_api.infrastructure.auth.passwords import BcryptPasswordHasher
from crm_api.infrastructure.auth.repositories import (
    SqlAlchemySessionRepository,
    SqlAlchemyUserRepository,
)
from crm_api.infrastructure.auth.tokens import Sha256SessionTokenHasher
from crm_api.infrastructure.database import get_database_session

_bearer_scheme = HTTPBearer(
    scheme_name="SessionToken",
    description="Token de sessão obtido em POST /auth/login.",
)

DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]


def _build_authenticate_user_use_case(
    session: AsyncSession,
) -> AuthenticateUserUseCase:
    return AuthenticateUserUseCase(
        users=SqlAlchemyUserRepository(session),
        sessions=SqlAlchemySessionRepository(session),
        password_hasher=BcryptPasswordHasher(),
        token_hasher=Sha256SessionTokenHasher(),
        session_ttl=timedelta(minutes=get_settings().session_ttl_minutes),
    )


def get_authenticate_user_use_case(
    session: DatabaseSession,
) -> AuthenticateUserUseCase:
    return _build_authenticate_user_use_case(session)


def get_setup_owner_use_case(session: DatabaseSession) -> SetupOwnerUseCase:
    users = SqlAlchemyUserRepository(session)
    password_hasher = BcryptPasswordHasher()
    return SetupOwnerUseCase(
        users=users,
        password_hasher=password_hasher,
        authenticate=AuthenticateUserUseCase(
            users=users,
            sessions=SqlAlchemySessionRepository(session),
            password_hasher=password_hasher,
            token_hasher=Sha256SessionTokenHasher(),
            session_ttl=timedelta(minutes=get_settings().session_ttl_minutes),
        ),
    )


def get_setup_status_use_case(session: DatabaseSession) -> GetSetupStatusUseCase:
    return GetSetupStatusUseCase(users=SqlAlchemyUserRepository(session))


def get_logout_use_case(session: DatabaseSession) -> LogoutUseCase:
    return LogoutUseCase(
        sessions=SqlAlchemySessionRepository(session),
        token_hasher=Sha256SessionTokenHasher(),
    )


def get_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
) -> str:
    return credentials.credentials


BearerToken = Annotated[str, Depends(get_bearer_token)]


async def get_current_user(
    session: DatabaseSession,
    session_token: BearerToken,
) -> User:
    use_case = GetCurrentUserUseCase(
        sessions=SqlAlchemySessionRepository(session),
        users=SqlAlchemyUserRepository(session),
        token_hasher=Sha256SessionTokenHasher(),
    )

    try:
        return await use_case.execute(session_token=session_token)
    except (InvalidSessionError, InactiveUserError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


CurrentUser = Annotated[User, Depends(get_current_user)]
