"""Entrada do sidecar FastAPI empacotado para o aplicativo Windows."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import threading
from contextlib import closing
from pathlib import Path
from socket import AF_INET, SOCK_STREAM, socket

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from crm_api.core.config import DOCUMENTS_DIRECTORY_NAME, get_settings
from crm_api.core.desktop_runtime import DesktopRuntime
from crm_api.infrastructure.documents.storage import provision_document_storage

_DATABASE_FILENAME = "crm.sqlite3"
_CANDIDATE_FILENAME = "crm.sqlite3.candidate"
_MAX_BOOTSTRAP_SECRET_BYTES = 256


def _api_root() -> Path:
    """Localiza arquivos Alembic tanto em fonte quanto no bundle `onedir`."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


def _database_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.resolve().as_posix()}"


def _alembic_config(database_path: Path) -> Config:
    root = _api_root()
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", _database_url(database_path))
    return config


def _verify_sqlite_file(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        integrity_result = connection.execute("PRAGMA integrity_check").fetchone()
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    if integrity_result != ("ok",) or foreign_key_errors:
        raise RuntimeError("local database integrity verification failed")


def _at_current_revision(path: Path) -> bool:
    config = _alembic_config(path)
    expected_revision = ScriptDirectory.from_config(config).get_current_head()
    with closing(sqlite3.connect(path)) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    return row == (expected_revision,)


def _upgrade_candidate(path: Path) -> None:
    previous_database_url = os.environ.get("DATABASE_URL")
    previous_silent_migrations = os.environ.get("DELTA_FORCE_SILENT_MIGRATIONS")
    os.environ["DATABASE_URL"] = _database_url(path)
    os.environ["DELTA_FORCE_SILENT_MIGRATIONS"] = "1"
    get_settings.cache_clear()
    try:
        command.upgrade(_alembic_config(path), "head")
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
        if previous_silent_migrations is None:
            os.environ.pop("DELTA_FORCE_SILENT_MIGRATIONS", None)
        else:
            os.environ["DELTA_FORCE_SILENT_MIGRATIONS"] = previous_silent_migrations
        get_settings.cache_clear()


def provision_desktop_database(data_directory: Path) -> Path:
    """Publica um banco novo só após migration e verificações locais concluírem."""
    data_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    active_path = data_directory / _DATABASE_FILENAME
    if active_path.exists():
        _verify_sqlite_file(active_path)
        if not _at_current_revision(active_path):
            raise RuntimeError("local database update requires a verified backup")
        return active_path

    candidate_path = data_directory / _CANDIDATE_FILENAME
    if candidate_path.exists():
        candidate_path.unlink()
    _upgrade_candidate(candidate_path)
    _verify_sqlite_file(candidate_path)
    candidate_path.replace(active_path)
    return active_path


def _read_bootstrap_secret() -> str:
    value = sys.stdin.buffer.readline(_MAX_BOOTSTRAP_SECRET_BYTES + 1).rstrip(b"\r\n")
    if not value or len(value) > _MAX_BOOTSTRAP_SECRET_BYTES:
        raise RuntimeError("desktop bootstrap input is invalid")
    try:
        secret = value.decode("ascii")
    except UnicodeDecodeError:
        raise RuntimeError("desktop bootstrap input is invalid") from None
    if not secret.isascii():
        raise RuntimeError("desktop bootstrap input is invalid")
    return secret


async def _serve(runtime: DesktopRuntime, listener: socket) -> None:
    import uvicorn

    from crm_api.main import create_app

    app = create_app(desktop_runtime=runtime)
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=runtime.port,
        workers=1,
        access_log=False,
        log_config=None,
        log_level="critical",
    )
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve(sockets=[listener]))
    while not server.started:
        if server_task.done():
            await server_task
            raise RuntimeError("desktop server failed to start")
        await asyncio.sleep(0.01)

    # Após ler o segredo de bootstrap, o stdin pertence ao supervisor Tauri.
    # EOF significa fechamento normal da janela: o Uvicorn recebe oportunidade
    # de concluir a escrita atual antes de o supervisor aplicar o fallback.
    threading.Thread(
        target=_stop_when_supervisor_disconnects,
        args=(server,),
        daemon=True,
    ).start()

    # É o único stdout do sidecar; não contém segredo, capability, caminho ou
    # dados do cliente. O supervisor só tenta o bootstrap depois deste sinal.
    sys.stdout.write(json.dumps({"event": "ready", "port": runtime.port}) + "\n")
    sys.stdout.flush()
    await server_task


def _stop_when_supervisor_disconnects(server: object) -> None:
    """Solicita o encerramento gracioso quando o supervisor fecha o stdin."""
    sys.stdin.buffer.read(1)
    setattr(server, "should_exit", True)


def main() -> None:
    """Lê o segredo por stdin e inicia uma API de uma única execução local."""
    data_directory_value = os.environ.get("DELTA_FORCE_DATA_DIR")
    if data_directory_value is None:
        raise RuntimeError("desktop data directory is missing")

    secret = _read_bootstrap_secret()
    data_directory = Path(data_directory_value)
    database_path = provision_desktop_database(data_directory)
    # Documentos ficam ao lado do banco, na mesma árvore privada, para que o
    # backup em HD externo (#44) trate banco e arquivos como uma unidade.
    provision_document_storage(data_directory / DOCUMENTS_DIRECTORY_NAME)
    os.environ["DATABASE_URL"] = _database_url(database_path)
    os.environ["CORS_ALLOWED_ORIGINS"] = "http://tauri.localhost"
    get_settings.cache_clear()

    listener = socket(AF_INET, SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.setblocking(False)
    port = int(listener.getsockname()[1])
    origin = os.environ.get("DELTA_FORCE_DESKTOP_ORIGIN", "http://tauri.localhost")
    os.environ["CORS_ALLOWED_ORIGINS"] = origin
    runtime = DesktopRuntime(bootstrap_secret=secret, port=port, origin=origin)
    del secret

    try:
        asyncio.run(_serve(runtime, listener))
    finally:
        listener.close()


if __name__ == "__main__":
    main()
