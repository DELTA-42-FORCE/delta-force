"""Contratos HTTP do módulo de autenticação."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


_BCRYPT_PASSWORD_MAX_BYTES = 72


def _validate_password_byte_length(password: str) -> str:
    if len(password.encode("utf-8")) > _BCRYPT_PASSWORD_MAX_BYTES:
        raise ValueError("password must be at most 72 UTF-8 bytes")
    return password


class SetupOwnerRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=12, max_length=72)

    _password_fits_bcrypt = field_validator("password")(_validate_password_byte_length)


class SetupStatusResponse(BaseModel):
    requires_setup: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

    _password_fits_bcrypt = field_validator("password")(_validate_password_byte_length)


class AuthenticatedUser(BaseModel):
    id: UUID
    email: str
    full_name: str


class LoginResponse(BaseModel):
    session_token: str
    expires_at: datetime
    user: AuthenticatedUser
