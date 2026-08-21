"""Loopback-only Uvicorn sidecar entrypoint for the Windows spike."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path
from collections.abc import Callable
from typing import BinaryIO, TextIO

import uvicorn
from fastapi import FastAPI

from spike_runtime.app import DEFAULT_TAURI_ORIGIN, create_app
from spike_runtime.security import RuntimeConfigurationError, RuntimeGate
from spike_runtime.sqlite_smoke import database_path_for, run_sqlite_smoke

LOOPBACK_HOST = "127.0.0.1"
MAX_BOOTSTRAP_TOKEN_BYTES = 256


def read_bootstrap_secret(stream: BinaryIO) -> str:
    """Read exactly one bounded base64url token line from an inherited stdin."""

    raw_line = stream.readline(MAX_BOOTSTRAP_TOKEN_BYTES + 2)
    if not raw_line or len(raw_line) > MAX_BOOTSTRAP_TOKEN_BYTES + 1:
        raise RuntimeConfigurationError("invalid bootstrap input")
    if not raw_line.endswith(b"\n"):
        raise RuntimeConfigurationError("invalid bootstrap input")

    encoded = raw_line[:-1]
    if encoded.endswith(b"\r"):
        encoded = encoded[:-1]
    try:
        return encoded.decode("ascii")
    except UnicodeDecodeError as exc:
        raise RuntimeConfigurationError("invalid bootstrap input") from exc


def reserve_loopback_socket() -> socket.socket:
    """Atomically reserve the runtime listener without a free-port race."""

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.set_inheritable(False)
        listener.bind((LOOPBACK_HOST, 0))
        listener.listen(socket.SOMAXCONN)
    except Exception:
        listener.close()
        raise
    return listener


def emit_runtime_ready(
    stream: TextIO,
    port: int,
    *,
    process_id: int | None = None,
) -> None:
    """Emit the only successful startup message, with technical fields only."""

    payload = {
        "event": "runtime-ready",
        "host": LOOPBACK_HOST,
        "pid": process_id if process_id is not None else os.getpid(),
        "port": port,
    }
    stream.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
    stream.flush()


def emit_runtime_error(stream: TextIO) -> None:
    payload = {"code": "startup-failed", "event": "runtime-error"}
    stream.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
    stream.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Issue 43 API sidecar spike")
    parser.add_argument(
        "--data-dir",
        required=True,
        type=Path,
        help="synthetic data directory outside the binary tree",
    )
    return parser


def build_server_config(app: FastAPI) -> uvicorn.Config:
    """Keep the sidecar single-process and suppress HTTP access logging."""

    return uvicorn.Config(
        app=app,
        host=LOOPBACK_HOST,
        port=0,
        workers=1,
        access_log=False,
        log_level="critical",
        server_header=False,
        date_header=False,
    )


class RuntimeServer(uvicorn.Server):
    """Announce readiness only after Uvicorn completed application startup."""

    def __init__(
        self,
        config: uvicorn.Config,
        *,
        on_started: Callable[[], None],
    ) -> None:
        super().__init__(config)
        self._on_started = on_started

    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        await super().startup(sockets=sockets)
        if self.started:
            self._on_started()


def run_sidecar(data_directory: Path, stdin: BinaryIO, stdout: TextIO) -> None:
    bootstrap_secret = read_bootstrap_secret(stdin)
    database_path = database_path_for(data_directory)
    run_sqlite_smoke(database_path)

    listener = reserve_loopback_socket()
    try:
        host, port = listener.getsockname()
        if host != LOOPBACK_HOST or port <= 0:
            raise RuntimeError("loopback reservation failed")

        gate = RuntimeGate(bootstrap_secret)
        del bootstrap_secret
        server: uvicorn.Server | None = None

        def request_shutdown() -> None:
            if server is None:
                raise RuntimeError("runtime server is not ready")
            server.should_exit = True

        app = create_app(
            gate,
            expected_host=f"{LOOPBACK_HOST}:{port}",
            shutdown_callback=request_shutdown,
            expected_origin=DEFAULT_TAURI_ORIGIN,
        )
        server = RuntimeServer(
            build_server_config(app),
            on_started=lambda: emit_runtime_ready(stdout, port),
        )
        server.run(sockets=[listener])
    finally:
        listener.close()


def main() -> int:
    options = build_parser().parse_args()
    try:
        run_sidecar(options.data_dir, sys.stdin.buffer, sys.stdout)
    except Exception:
        emit_runtime_error(sys.stdout)
        return 1
    return 0
