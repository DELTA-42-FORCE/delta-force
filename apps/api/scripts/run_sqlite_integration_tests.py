"""Executa migrations e testes de integração em um arquivo SQLite descartável."""

import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


def run() -> None:
    with tempfile.TemporaryDirectory(prefix="delta_force_integration_") as directory:
        database_path = (
            Path(directory) / f"delta_force_integration_{uuid.uuid4().hex}.sqlite3"
        )
        database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"

        environment = os.environ.copy()
        environment["DATABASE_URL"] = database_url

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


if __name__ == "__main__":
    run()
