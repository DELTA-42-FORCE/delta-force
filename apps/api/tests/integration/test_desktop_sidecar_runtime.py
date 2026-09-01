"""Smoke test do sidecar local com banco, autenticação e auditoria reais."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path
from queue import Queue
from urllib.error import HTTPError
from urllib.request import Request, urlopen

_ORIGIN = "http://tauri.localhost"
_SECRET = "synthetic-desktop-bootstrap-secret"


def _read_ready_line(process: subprocess.Popen[bytes]) -> bytes:
    assert process.stdout is not None
    lines: Queue[bytes] = Queue(maxsize=1)
    threading.Thread(
        target=lambda: lines.put(process.stdout.readline()), daemon=True
    ).start()
    try:
        return lines.get(timeout=15)
    except Exception as error:
        raise AssertionError("desktop sidecar did not publish readiness") from error


def _request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str],
    payload: dict[str, str] | None = None,
) -> tuple[int, dict[str, object]]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 -- loopback only
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def _stop_gracefully(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    assert process.stdin is not None
    process.stdin.close()
    assert process.wait(timeout=5) == 0


def test_desktop_sidecar_bootstraps_and_records_owner_setup_audit_event(
    tmp_path: Path,
) -> None:
    data_directory = tmp_path / "local-data"
    environment = os.environ | {
        "DELTA_FORCE_DATA_DIR": str(data_directory),
        "DELTA_FORCE_DESKTOP_ORIGIN": _ORIGIN,
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "crm_api.desktop_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    try:
        assert process.stdin is not None
        process.stdin.write(f"{_SECRET}\n".encode())
        process.stdin.flush()

        readiness = json.loads(_read_ready_line(process))
        assert readiness["event"] == "ready"
        port = readiness["port"]
        assert isinstance(port, int) and port > 0
        base_url = f"http://127.0.0.1:{port}"
        source_headers = {"Host": f"127.0.0.1:{port}", "Origin": _ORIGIN}

        denied_status, _ = _request(f"{base_url}/health", headers=source_headers)
        bootstrap_status, bootstrap = _request(
            f"{base_url}/_desktop/bootstrap",
            method="POST",
            headers={**source_headers, "X-Delta-Desktop-Secret": _SECRET},
        )
        assert denied_status == 403
        assert bootstrap_status == 200
        capability = bootstrap["capability"]
        assert isinstance(capability, str) and capability

        setup_status, setup = _request(
            f"{base_url}/auth/setup",
            method="POST",
            headers={
                **source_headers,
                "Content-Type": "application/json",
                "X-Delta-Desktop-Capability": capability,
            },
            payload={
                "email": "owner@example.com",
                "full_name": "Synthetic Owner",
                "password": "synthetic-owner-password",
            },
        )
        assert setup_status == 201
        session_token = setup["session_token"]
        assert isinstance(session_token, str) and session_token

        create_status, client = _request(
            f"{base_url}/clients",
            method="POST",
            headers={
                **source_headers,
                "Content-Type": "application/json",
                "Authorization": f"Bearer {session_token}",
                "X-Delta-Desktop-Capability": capability,
            },
            payload={"display_name": "Cliente Desktop Sintético"},
        )
        assert create_status == 201
        assert client["display_name"] == "Cliente Desktop Sintético"
    finally:
        _stop_gracefully(process)

    with sqlite3.connect(data_directory / "crm.sqlite3") as connection:
        actions = connection.execute("SELECT action FROM audit_events").fetchall()
    assert ("auth.owner_setup",) in actions
