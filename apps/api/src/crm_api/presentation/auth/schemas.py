"""Contratos HTTP do módulo de autenticação."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthenticatedUser(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_admin: bool


class LoginResponse(BaseModel):
    session_token: str
    expires_at: datetime
    user: AuthenticatedUser
