"""Contratos HTTP do módulo de autenticação."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class SetupOwnerRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=12, max_length=128)


class SetupStatusResponse(BaseModel):
    requires_setup: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthenticatedUser(BaseModel):
    id: UUID
    email: str
    full_name: str


class LoginResponse(BaseModel):
    session_token: str
    expires_at: datetime
    user: AuthenticatedUser
