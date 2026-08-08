"""Leitura tipada de configurações da API."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]


class Settings(BaseSettings):
    """Configurações necessárias para adaptadores de infraestrutura."""

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str

    @field_validator("database_url")
    @classmethod
    def database_url_uses_async_psycopg(cls, value: str) -> str:
        """Garante o driver assíncrono padronizado para PostgreSQL."""
        if not value.startswith("postgresql+psycopg://"):
            message = "DATABASE_URL must use postgresql+psycopg://"
            raise ValueError(message)
        return value


@lru_cache
def get_settings() -> Settings:
    """Retorna configurações validadas uma vez por processo."""
    return Settings()
