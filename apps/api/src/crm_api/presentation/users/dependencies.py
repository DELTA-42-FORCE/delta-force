"""Dependências FastAPI da gestão de usuários: exige sessão de administrador."""

from typing import Annotated

from fastapi import Depends, HTTPException, status

from crm_api.application.users.create_user import CreateUserUseCase
from crm_api.application.users.list_users import ListUsersUseCase
from crm_api.application.users.set_user_active import SetUserActiveUseCase
from crm_api.application.users.update_user import UpdateUserUseCase
from crm_api.domain.auth.entities import User
from crm_api.infrastructure.auth.passwords import BcryptPasswordHasher
from crm_api.infrastructure.auth.repositories import SqlAlchemyUserRepository
from crm_api.presentation.auth.dependencies import CurrentUser, DatabaseSession


async def require_admin(current_user: CurrentUser) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin privileges required",
        )

    return current_user


AdminUser = Annotated[User, Depends(require_admin)]


def get_create_user_use_case(session: DatabaseSession) -> CreateUserUseCase:
    return CreateUserUseCase(
        users=SqlAlchemyUserRepository(session),
        password_hasher=BcryptPasswordHasher(),
    )


def get_list_users_use_case(session: DatabaseSession) -> ListUsersUseCase:
    return ListUsersUseCase(users=SqlAlchemyUserRepository(session))


def get_update_user_use_case(session: DatabaseSession) -> UpdateUserUseCase:
    return UpdateUserUseCase(users=SqlAlchemyUserRepository(session))


def get_set_user_active_use_case(session: DatabaseSession) -> SetUserActiveUseCase:
    return SetUserActiveUseCase(users=SqlAlchemyUserRepository(session))
