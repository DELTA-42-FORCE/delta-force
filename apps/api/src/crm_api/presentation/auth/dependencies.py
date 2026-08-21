"""Dependências FastAPI que fiam os casos de uso de autenticação aos adaptadores."""

from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.auth.authenticate_user import AuthenticateUserUseCase
from crm_api.application.auth.get_current_user import GetCurrentUserUseCase
from crm_api.application.auth.logout import LogoutUseCase
from crm_api.application.auth.session_issuer import SessionIssuer
from crm_api.application.auth.setup_owner import (
    GetSetupStatusUseCase,
    SetupOwnerUseCase,
)
from crm_api.application.auth.view_owner_profile import ViewOwnerProfileUseCase
from crm_api.core.config import get_settings
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.auth.entities import User
from crm_api.domain.auth.errors import InactiveUserError, InvalidSessionError
from crm_api.infrastructure.auth.passwords import BcryptPasswordHasher
from crm_api.infrastructure.auth.repositories import (
    SqlAlchemySessionRepository,
    SqlAlchemyUserRepository,
)
from crm_api.infrastructure.auth.tokens import Sha256SessionTokenHasher
from crm_api.infrastructure.audit.repositories import (
    SqlAlchemyAuditEventRepository,
)
from crm_api.infrastructure.audit.transactions import SqlAlchemyTransaction
from crm_api.presentation.dependencies import DatabaseSession

_bearer_scheme = HTTPBearer(
    scheme_name="SessionToken",
    description="Token de sessão obtido em POST /auth/login.",
    auto_error=False,
)


def _build_audit(session: DatabaseSession) -> RecordAuditEventUseCase:
    return RecordAuditEventUseCase(events=SqlAlchemyAuditEventRepository(session))


def _build_session_issuer(session: DatabaseSession) -> SessionIssuer:
    return SessionIssuer(
        sessions=SqlAlchemySessionRepository(session),
        token_hasher=Sha256SessionTokenHasher(),
        session_ttl=timedelta(minutes=get_settings().session_ttl_minutes),
    )


def _build_authenticate_user_use_case(
    session: DatabaseSession,
) -> AuthenticateUserUseCase:
    return AuthenticateUserUseCase(
        users=SqlAlchemyUserRepository(session),
        password_hasher=BcryptPasswordHasher(),
        session_issuer=_build_session_issuer(session),
        audit=_build_audit(session),
        transaction=SqlAlchemyTransaction(session),
    )


def get_authenticate_user_use_case(
    session: DatabaseSession,
) -> AuthenticateUserUseCase:
    return _build_authenticate_user_use_case(session)


def get_setup_owner_use_case(session: DatabaseSession) -> SetupOwnerUseCase:
    return SetupOwnerUseCase(
        users=SqlAlchemyUserRepository(session),
        password_hasher=BcryptPasswordHasher(),
        session_issuer=_build_session_issuer(session),
        audit=_build_audit(session),
        transaction=SqlAlchemyTransaction(session),
    )


def get_setup_status_use_case(session: DatabaseSession) -> GetSetupStatusUseCase:
    return GetSetupStatusUseCase(users=SqlAlchemyUserRepository(session))


def get_logout_use_case(session: DatabaseSession) -> LogoutUseCase:
    return LogoutUseCase(
        sessions=SqlAlchemySessionRepository(session),
        token_hasher=Sha256SessionTokenHasher(),
        audit=_build_audit(session),
        transaction=SqlAlchemyTransaction(session),
    )


def get_view_owner_profile_use_case(
    session: DatabaseSession,
) -> ViewOwnerProfileUseCase:
    return ViewOwnerProfileUseCase(
        audit=_build_audit(session),
        transaction=SqlAlchemyTransaction(session),
    )


def get_bearer_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
) -> str | None:
    return credentials.credentials if credentials is not None else None


BearerToken = Annotated[str | None, Depends(get_bearer_token)]


async def get_current_user(
    request: Request,
    session: DatabaseSession,
    session_token: BearerToken,
) -> User:
    use_case = GetCurrentUserUseCase(
        sessions=SqlAlchemySessionRepository(session),
        users=SqlAlchemyUserRepository(session),
        token_hasher=Sha256SessionTokenHasher(),
    )

    try:
        if session_token is None:
            raise InvalidSessionError
        return await use_case.execute(session_token=session_token)
    except (InvalidSessionError, InactiveUserError):
        route = request.scope.get("route")
        route_template = str(getattr(route, "path", "/unmatched"))
        transaction = SqlAlchemyTransaction(session)
        try:
            await _build_audit(session).execute(
                actor_kind=AuditActorKind.ANONYMOUS,
                actor_user_id=None,
                action=AuditAction.ACCESS_DENIED,
                resource_type=AuditResourceType.ROUTE,
                resource_id=None,
                result=AuditResult.DENIED,
                context={
                    "route_template": route_template,
                    "http_method": request.method,
                    "reason_code": "invalid_session",
                },
            )
            await transaction.commit()
        except Exception:
            await transaction.rollback()
            raise
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


CurrentUser = Annotated[User, Depends(get_current_user)]
