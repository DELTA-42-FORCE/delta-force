"""Caso de uso de login: emite uma sessão para uma conta interna válida."""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from crm_api.domain.auth.entities import Session, User
from crm_api.domain.auth.errors import InactiveUserError, InvalidCredentialsError
from crm_api.domain.auth.repositories import (
    PasswordHasher,
    SessionRepository,
    UserRepository,
)


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    """Par usuário/sessão devolvido por um login bem-sucedido."""

    user: User
    session: Session


@dataclass(frozen=True, slots=True)
class AuthenticateUserUseCase:
    """Valida credenciais e cria uma sessão de acesso."""

    users: UserRepository
    sessions: SessionRepository
    password_hasher: PasswordHasher
    session_ttl: timedelta

    async def execute(self, *, email: str, password: str) -> AuthenticationResult:
        user = await self.users.find_by_email(email)
        password_hash = (
            user.password_hash if user is not None else self.password_hasher.dummy_hash
        )
        credentials_match = self.password_hasher.verify(
            password=password, password_hash=password_hash
        )

        if user is None or not credentials_match:
            raise InvalidCredentialsError

        if not user.is_active:
            raise InactiveUserError

        session = await self.sessions.create(
            token=secrets.token_urlsafe(32),
            user_id=user.id,
            expires_at=datetime.now(UTC) + self.session_ttl,
        )
        return AuthenticationResult(user=user, session=session)
