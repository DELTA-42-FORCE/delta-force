"""Exercise the packaged sidecar without printing runtime credentials."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import queue
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
from contextlib import closing
from pathlib import Path
from typing import Any, TextIO

EXPECTED_ORIGIN = "http://tauri.localhost"
BOOTSTRAP_HEADER = "X-Runtime-Bootstrap"
CAPABILITY_HEADER = "X-Runtime-Capability"


def _readline(stream: TextIO, destination: queue.Queue[str]) -> None:
    destination.put(stream.readline())


def _request(
    connection: http.client.HTTPConnection,
    method: str,
    path: str,
    *,
    headers: dict[str, str],
) -> tuple[int, dict[str, Any]]:
    connection.request(method, path, body=b"", headers=headers)
    response = connection.getresponse()
    payload = response.read()
    parsed = json.loads(payload) if payload else {}
    return response.status, parsed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _listeners_for_process(process_id: int) -> list[dict[str, Any]]:
    if sys.platform != "win32":
        raise RuntimeError("listener enumeration is only defined for Windows")

    windows_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    powershell = (
        windows_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    )
    script = (
        "$ErrorActionPreference = 'Stop'; "
        f"$items = @(Get-NetTCPConnection -State Listen | Where-Object "
        f"{{ $_.OwningProcess -eq {process_id} }} | Select-Object "
        "LocalAddress,LocalPort,OwningProcess); "
        "ConvertTo-Json -InputObject $items -Compress"
    )
    completed = subprocess.run(
        [
            str(powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10.0,
    )
    listeners = json.loads(completed.stdout)
    if not isinstance(listeners, list):
        raise RuntimeError("listener enumeration returned an invalid shape")
    return listeners


def _start_sidecar(
    executable: Path,
    data_directory: Path,
    bootstrap_secret: str,
) -> tuple[subprocess.Popen[str], dict[str, Any], str]:
    command = [str(executable), "--data-dir", str(data_directory)]
    if bootstrap_secret in command:
        raise RuntimeError("bootstrap secret entered the process arguments")

    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        creationflags=creation_flags,
    )
    if process.stdin is None or process.stdout is None or process.stderr is None:
        process.kill()
        process.wait(timeout=5.0)
        raise RuntimeError("failed to create private sidecar pipes")

    try:
        process.stdin.write(f"{bootstrap_secret}\n")
        process.stdin.flush()
        process.stdin.close()

        ready_lines: queue.Queue[str] = queue.Queue(maxsize=1)
        reader = threading.Thread(
            target=_readline,
            args=(process.stdout, ready_lines),
            daemon=True,
        )
        reader.start()
        ready_line = ready_lines.get(timeout=15.0)
        ready = json.loads(ready_line)
        if set(ready) != {"event", "host", "pid", "port"}:
            raise RuntimeError("unexpected sidecar readiness contract")
        if ready["event"] != "runtime-ready":
            raise RuntimeError("sidecar did not become ready")
        if ready["host"] != "127.0.0.1":
            raise RuntimeError("sidecar reported a non-loopback listener")
        if ready["pid"] != process.pid:
            raise RuntimeError("sidecar readiness PID does not match its process")
        if not isinstance(ready["port"], int) or ready["port"] <= 0:
            raise RuntimeError("sidecar reported an invalid port")

        listeners = _listeners_for_process(process.pid)
        expected_listener = {
            "LocalAddress": "127.0.0.1",
            "LocalPort": ready["port"],
            "OwningProcess": process.pid,
        }
        if listeners != [expected_listener]:
            raise RuntimeError("sidecar owns an unexpected TCP listener")
        return process, ready, ready_line
    except Exception:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5.0)
        raise


def _finish_sidecar(
    process: subprocess.Popen[str],
    ready: dict[str, Any],
    ready_line: str,
    credentials: tuple[str, ...],
) -> None:
    if process.stdout is None or process.stderr is None:
        raise RuntimeError("sidecar output pipes are unavailable")
    if process.wait(timeout=10.0) != 0:
        raise RuntimeError("sidecar returned a non-zero exit code")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
        probe_socket.settimeout(1.0)
        if probe_socket.connect_ex(("127.0.0.1", ready["port"])) == 0:
            raise RuntimeError("sidecar listener remained open after shutdown")

    remaining_stdout = process.stdout.read()
    stderr = process.stderr.read()
    emitted = ready_line + remaining_stdout + stderr
    if remaining_stdout or stderr:
        raise RuntimeError("sidecar emitted unexpected console output")
    if any(credential and credential in emitted for credential in credentials):
        raise RuntimeError("runtime credential appeared in process output")


def _verify_stale_capability_rejected(
    executable: Path,
    data_directory: Path,
    stale_capability: str,
) -> None:
    bootstrap_secret = secrets.token_urlsafe(32)
    process, ready, ready_line = _start_sidecar(
        executable,
        data_directory,
        bootstrap_secret,
    )
    current_capability = ""
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            ready["port"],
            timeout=5.0,
        )
        try:
            base_headers = {"Origin": EXPECTED_ORIGIN}
            status, payload = _request(
                connection,
                "POST",
                "/runtime/bootstrap",
                headers={**base_headers, BOOTSTRAP_HEADER: bootstrap_secret},
            )
            if status != 200 or set(payload) != {"capability"}:
                raise RuntimeError("second runtime bootstrap failed")
            current_capability = payload["capability"]

            status, _ = _request(
                connection,
                "GET",
                "/runtime/probe",
                headers={
                    **base_headers,
                    CAPABILITY_HEADER: stale_capability,
                },
            )
            if status != 401:
                raise RuntimeError("runtime accepted a capability from another run")

            status, _ = _request(
                connection,
                "POST",
                "/runtime/shutdown",
                headers={
                    **base_headers,
                    CAPABILITY_HEADER: current_capability,
                },
            )
            if status != 202:
                raise RuntimeError("second runtime shutdown was rejected")
        finally:
            connection.close()

        _finish_sidecar(
            process,
            ready,
            ready_line,
            (bootstrap_secret, current_capability, stale_capability),
        )
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5.0)


def verify(executable: Path) -> dict[str, Any]:
    executable = executable.resolve(strict=True)
    runtime_directory = executable.parent / "api-runtime"
    if executable.suffix.lower() != ".exe" or not runtime_directory.is_dir():
        raise RuntimeError("artifact is not the expected PyInstaller onedir layout")

    artifact_files = sorted(
        path for path in executable.parent.rglob("*") if path.is_file()
    )
    if len(artifact_files) < 2:
        raise RuntimeError("onedir artifact is unexpectedly empty")

    bootstrap_secret = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix="delta-force-issue-43-") as temporary:
        temporary_root = Path(temporary)
        data_directory = temporary_root / "synthetic-state-first"
        process, ready, ready_line = _start_sidecar(
            executable,
            data_directory,
            bootstrap_secret,
        )
        capability = ""
        try:
            base_headers = {"Origin": EXPECTED_ORIGIN}
            connection = http.client.HTTPConnection(
                "127.0.0.1",
                ready["port"],
                timeout=5.0,
            )
            try:
                bootstrap_headers = {
                    **base_headers,
                    BOOTSTRAP_HEADER: bootstrap_secret,
                }
                status, _ = _request(
                    connection,
                    "POST",
                    "/runtime/bootstrap",
                    headers={
                        **bootstrap_headers,
                        "Host": f"localhost:{ready['port']}",
                    },
                )
                if status != 400:
                    raise RuntimeError("runtime accepted an invalid Host")

                status, _ = _request(
                    connection,
                    "POST",
                    "/runtime/bootstrap",
                    headers={
                        **bootstrap_headers,
                        "Origin": "https://example.invalid",
                    },
                )
                if status != 403:
                    raise RuntimeError("runtime accepted an invalid Origin")

                status, payload = _request(
                    connection,
                    "POST",
                    "/runtime/bootstrap",
                    headers=bootstrap_headers,
                )
                if status != 200 or set(payload) != {"capability"}:
                    raise RuntimeError("runtime bootstrap failed")
                capability = payload["capability"]
                if not isinstance(capability, str) or len(capability) < 43:
                    raise RuntimeError("runtime returned an invalid capability")

                status, _ = _request(
                    connection,
                    "POST",
                    "/runtime/bootstrap",
                    headers=bootstrap_headers,
                )
                if status != 401:
                    raise RuntimeError("runtime accepted a reused bootstrap secret")

                status, _ = _request(
                    connection,
                    "GET",
                    "/runtime/probe",
                    headers=base_headers,
                )
                if status != 401:
                    raise RuntimeError("runtime accepted a missing capability")

                status, _ = _request(
                    connection,
                    "GET",
                    "/runtime/probe",
                    headers={
                        **base_headers,
                        CAPABILITY_HEADER: "invalid",
                    },
                )
                if status != 401:
                    raise RuntimeError("runtime accepted an invalid capability")

                authorized_headers = {
                    **base_headers,
                    CAPABILITY_HEADER: capability,
                }
                status, payload = _request(
                    connection,
                    "GET",
                    "/runtime/probe",
                    headers=authorized_headers,
                )
                if status != 200 or payload != {"status": "ok"}:
                    raise RuntimeError("authorized runtime probe failed")

                status, _ = _request(
                    connection,
                    "POST",
                    "/runtime/shutdown",
                    headers=authorized_headers,
                )
                if status != 202:
                    raise RuntimeError("graceful runtime shutdown was rejected")
            finally:
                connection.close()

            _finish_sidecar(
                process,
                ready,
                ready_line,
                (bootstrap_secret, capability),
            )

            database_path = data_directory / "runtime-smoke.sqlite3"
            if not database_path.is_file():
                raise RuntimeError("SQLite database was not created outside binaries")
            if database_path.is_relative_to(executable.parent):
                raise RuntimeError("SQLite database overlaps the binary tree")
            with closing(sqlite3.connect(database_path)) as database:
                integrity = database.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError("packaged SQLite integrity check failed")

            _verify_stale_capability_rejected(
                executable,
                temporary_root / "synthetic-state-second",
                capability,
            )

            return {
                "artifact": {
                    "executable_sha256": _sha256(executable),
                    "file_count": len(artifact_files),
                    "layout": "pyinstaller-onedir",
                },
                "checks": {
                    "bootstrap_one_shot": "passed",
                    "capability_execution_scoped": "passed",
                    "capability_required": "passed",
                    "graceful_shutdown": "passed",
                    "host_origin_exact": "passed",
                    "loopback_ephemeral": "passed",
                    "os_listener_enumeration": "passed",
                    "output_sanitized": "passed",
                    "sqlite_external_integrity": "passed",
                },
                "runtime": {
                    "host": ready["host"],
                    "pid": ready["pid"],
                    "port": ready["port"],
                },
            }
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", required=True, type=Path)
    options = parser.parse_args()
    result = verify(options.executable)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
