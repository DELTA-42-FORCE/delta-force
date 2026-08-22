"""Dependências compartilhadas pela borda HTTP da API."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from crm_api.infrastructure.database import get_database_session

DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]
