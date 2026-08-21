import json
import queue
import secrets
import socket
import subprocess
import sys
import threading
from pathlib import Path

import httpx

from spike_runtime.app import (
    BOOTSTRAP_HEADER,
    CAPABILITY_HEADER,
    DEFAULT_TAURI_ORIGIN,
)


def _readline_in_background(
    stream,
    destination: queue.Queue[str],
) -> None:
    destination.put(stream.readline())


def test_live_sidecar_bootstrap_probe_and_graceful_shutdown(
    tmp_path: Path,
) -> None:
    bootstrap_secret = secrets.token_urlsafe(32)
    command = [
        sys.executable,
        "-m",
        "spike_runtime",
        "--data-dir",
        str(tmp_path / "synthetic-state"),
    ]
    assert bootstrap_secret not in command

    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    process = subprocess.Popen(
        command,
        cwd=Path(__file__).resolve().parents[1],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        creationflags=creation_flags,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None

    try:
        process.stdin.write(f"{bootstrap_secret}\n")
        process.stdin.flush()
        process.stdin.close()

        ready_lines: queue.Queue[str] = queue.Queue(maxsize=1)
        reader = threading.Thread(
            target=_readline_in_background,
            args=(process.stdout, ready_lines),
            daemon=True,
        )
        reader.start()
        ready_line = ready_lines.get(timeout=10.0)
        ready = json.loads(ready_line)

        assert ready == {
            "event": "runtime-ready",
            "host": "127.0.0.1",
            "pid": ready["pid"],
            "port": ready["port"],
        }
        assert isinstance(ready["pid"], int)
        assert ready["pid"] > 0
        assert isinstance(ready["port"], int)
        assert ready["port"] > 0
        assert bootstrap_secret not in ready_line

        base_url = f"http://127.0.0.1:{ready['port']}"
        with httpx.Client(
            base_url=base_url,
            headers={"Origin": DEFAULT_TAURI_ORIGIN},
            timeout=5.0,
        ) as client:
            bootstrap = client.post(
                "/runtime/bootstrap",
                headers={BOOTSTRAP_HEADER: bootstrap_secret},
            )
            assert bootstrap.status_code == 200
            capability = bootstrap.json()["capability"]

            denied = client.get("/runtime/probe")
            assert denied.status_code == 401

            authorized_headers = {CAPABILITY_HEADER: capability}
            probe = client.get(
                "/runtime/probe",
                headers=authorized_headers,
            )
            assert probe.status_code == 200
            assert probe.json() == {"status": "ok"}

            shutdown = client.post(
                "/runtime/shutdown",
                headers=authorized_headers,
            )
            assert shutdown.status_code == 202

        assert process.wait(timeout=10.0) == 0
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
            probe_socket.settimeout(1.0)
            assert probe_socket.connect_ex(("127.0.0.1", ready["port"])) != 0
        remaining_stdout = process.stdout.read()
        stderr = process.stderr.read()
        assert remaining_stdout == ""
        assert stderr == ""
        assert bootstrap_secret not in remaining_stdout
        assert bootstrap_secret not in stderr
        assert capability not in remaining_stdout
        assert capability not in stderr
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5.0)
