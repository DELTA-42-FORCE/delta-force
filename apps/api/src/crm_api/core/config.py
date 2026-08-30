"""Leitura tipada de configurações da API."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]

SUPPORTED_DATABASE_URL_PREFIXES = (
    "sqlite+aiosqlite://",
    "postgresql+psycopg://",
)


class Settings(BaseSettings):
    """Configurações necessárias para adaptadores de infraestrutura."""

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    session_ttl_minutes: int = 12 * 60
    cors_allowed_origins: str = "http://localhost:5173"

    @field_validator("database_url")
    @classmethod
    def database_url_uses_a_supported_async_driver(cls, value: str) -> str:
        """Aceita SQLite (alvo da ADR 0003) e PostgreSQL (fundação legada da #54)."""
        if not value.startswith(SUPPORTED_DATABASE_URL_PREFIXES):
            message = (
                "DATABASE_URL must use sqlite+aiosqlite:// or, during the "
                "PostgreSQL transition (#54), postgresql+psycopg://"
            )
            raise ValueError(message)
        return value

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Retorna configurações validadas uma vez por processo."""
    return Settings()
