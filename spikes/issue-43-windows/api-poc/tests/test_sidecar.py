import base64
import io
import json

import pytest
from fastapi import FastAPI

from spike_runtime.security import RuntimeConfigurationError
from spike_runtime.sidecar import (
    LOOPBACK_HOST,
    build_server_config,
    emit_runtime_error,
    emit_runtime_ready,
    read_bootstrap_secret,
    reserve_loopback_socket,
)


def token_for(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def test_bootstrap_secret_is_read_only_from_a_bounded_stdin_line() -> None:
    secret = token_for(b"bootstrap" * 4)
    assert read_bootstrap_secret(io.BytesIO(f"{secret}\r\n".encode())) == secret

    with pytest.raises(RuntimeConfigurationError):
        read_bootstrap_secret(io.BytesIO(secret.encode()))


def test_sidecar_reserves_only_an_ephemeral_ipv4_loopback_listener() -> None:
    listener = reserve_loopback_socket()
    try:
        host, port = listener.getsockname()
        assert host == LOOPBACK_HOST
        assert port > 0
    finally:
        listener.close()


def test_uvicorn_is_single_worker_and_has_no_access_or_server_logs() -> None:
    config = build_server_config(FastAPI())

    assert config.host == LOOPBACK_HOST
    assert config.port == 0
    assert config.workers == 1
    assert config.access_log is False
    assert config.log_level == "critical"
    assert config.server_header is False
    assert config.date_header is False


def test_stdout_events_are_sanitized_technical_json() -> None:
    output = io.StringIO()
    emit_runtime_ready(output, 43123, process_id=1234)
    emit_runtime_error(output)
    events = [json.loads(line) for line in output.getvalue().splitlines()]

    assert events == [
        {
            "event": "runtime-ready",
            "host": LOOPBACK_HOST,
            "pid": 1234,
            "port": 43123,
        },
        {"code": "startup-failed", "event": "runtime-error"},
    ]
