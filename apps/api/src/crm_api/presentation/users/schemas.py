"""Contratos HTTP da gestão de usuários autorizados."""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1)
    password: str = Field(min_length=8)
    is_admin: bool = False


class UpdateUserRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1)
    is_admin: bool | None = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_active: bool
    is_admin: bool
