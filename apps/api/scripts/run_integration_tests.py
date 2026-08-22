"""Executa migrations e testes em um banco PostgreSQL local descartável."""

import os
import subprocess
import sys
import uuid
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql

from crm_api.core.config import get_settings
from crm_api.core.database_url_safety import ensure_loopback_database_url


def replace_database(url: str, database: str) -> str:
    """Troca somente o nome do banco em uma URL SQLAlchemy psycopg."""
    parsed = urlsplit(url)
    return urlunsplit(
        (parsed.scheme, parsed.netloc, f"/{database}", parsed.query, parsed.fragment)
    )


def psycopg_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def run() -> None:
    base_url = get_settings().database_url
    ensure_loopback_database_url(base_url)
    database_name = f"delta_force_integration_{uuid.uuid4().hex}"
    admin_url = psycopg_url(replace_database(base_url, "postgres"))
    test_url = replace_database(base_url, database_name)

    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
        )

    environment = os.environ.copy()
    environment["DATABASE_URL"] = test_url
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=True,
            env=environment,
        )
        subprocess.run(
            [sys.executable, "-m", "pytest", "-m", "integration"],
            check=True,
            env=environment,
        )
    finally:
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    sql.Identifier(database_name)
                )
            )


if __name__ == "__main__":
    run()
