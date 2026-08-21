import base64
from collections.abc import Callable

from fastapi.testclient import TestClient

from spike_runtime.app import (
    BOOTSTRAP_HEADER,
    CAPABILITY_HEADER,
    DEFAULT_TAURI_ORIGIN,
    create_app,
)
from spike_runtime.security import RuntimeGate

EXPECTED_HOST = "127.0.0.1:43123"


def token_for(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def boundary_headers(**extra: str) -> dict[str, str]:
    return {
        "Host": EXPECTED_HOST,
        "Origin": DEFAULT_TAURI_ORIGIN,
        **extra,
    }


def _noop_shutdown() -> None:
    pass


def make_client(
    shutdown_callback: Callable[[], None] | None = None,
) -> tuple[TestClient, str, str]:
    bootstrap = token_for(b"bootstrap" * 4)
    capability = token_for(b"capability" * 4)
    gate = RuntimeGate(
        bootstrap,
        clock=lambda: 100.0,
        capability_factory=lambda: capability,
    )
    app = create_app(
        gate,
        expected_host=EXPECTED_HOST,
        shutdown_callback=shutdown_callback or _noop_shutdown,
    )
    return TestClient(app), bootstrap, capability


def test_bootstrap_is_single_use_and_returns_no_store_capability() -> None:
    client, bootstrap, capability = make_client()
    headers = boundary_headers(**{BOOTSTRAP_HEADER: bootstrap})

    response = client.post("/runtime/bootstrap", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"capability": capability}
    assert response.headers["cache-control"] == "no-store"

    reused = client.post("/runtime/bootstrap", headers=headers)
    assert reused.status_code == 401
    assert reused.json() == {"detail": "request rejected"}


def test_every_non_bootstrap_route_requires_the_capability() -> None:
    client, bootstrap, capability = make_client()
    client.post(
        "/runtime/bootstrap",
        headers=boundary_headers(**{BOOTSTRAP_HEADER: bootstrap}),
    )

    assert client.get("/runtime/probe", headers=boundary_headers()).status_code == 401
    assert (
        client.get(
            "/runtime/probe",
            headers=boundary_headers(**{CAPABILITY_HEADER: "invalid"}),
        ).status_code
        == 401
    )
    assert client.get(
        "/runtime/probe",
        headers=boundary_headers(**{CAPABILITY_HEADER: capability}),
    ).json() == {"status": "ok"}
    assert client.get("/unknown", headers=boundary_headers()).status_code == 401
    assert (
        client.get(
            "/unknown",
            headers=boundary_headers(**{CAPABILITY_HEADER: capability}),
        ).status_code
        == 404
    )


def test_cors_preflight_allows_only_the_exact_method_and_header_set() -> None:
    client, _, _ = make_client()
    allowed = client.options(
        "/runtime/probe",
        headers=boundary_headers(
            **{
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": CAPABILITY_HEADER,
            }
        ),
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == DEFAULT_TAURI_ORIGIN
    assert CAPABILITY_HEADER in allowed.headers["access-control-allow-headers"].lower()

    denied_method = client.options(
        "/runtime/probe",
        headers=boundary_headers(
            **{
                "Access-Control-Request-Method": "DELETE",
                "Access-Control-Request-Headers": CAPABILITY_HEADER,
            }
        ),
    )
    assert denied_method.status_code == 400

    denied_header = client.options(
        "/runtime/probe",
        headers=boundary_headers(
            **{
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            }
        ),
    )
    assert denied_header.status_code == 400


def test_preflight_still_requires_exact_host_and_origin() -> None:
    client, _, _ = make_client()
    request_headers = {
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": CAPABILITY_HEADER,
    }

    assert (
        client.options(
            "/runtime/probe",
            headers={
                "Host": "localhost:43123",
                "Origin": DEFAULT_TAURI_ORIGIN,
                **request_headers,
            },
        ).status_code
        == 400
    )
    assert (
        client.options(
            "/runtime/probe",
            headers={
                "Host": EXPECTED_HOST,
                "Origin": "https://example.invalid",
                **request_headers,
            },
        ).status_code
        == 403
    )


def test_host_and_origin_are_exact_allowlists() -> None:
    client, bootstrap, _ = make_client()

    bad_host = client.post(
        "/runtime/bootstrap",
        headers={
            "Host": "localhost:43123",
            "Origin": DEFAULT_TAURI_ORIGIN,
            BOOTSTRAP_HEADER: bootstrap,
        },
    )
    assert bad_host.status_code == 400

    bad_origin = client.post(
        "/runtime/bootstrap",
        headers={
            "Host": EXPECTED_HOST,
            "Origin": "https://example.invalid",
            BOOTSTRAP_HEADER: bootstrap,
        },
    )
    assert bad_origin.status_code == 403


def test_openapi_and_documentation_routes_are_disabled() -> None:
    client, bootstrap, capability = make_client()
    client.post(
        "/runtime/bootstrap",
        headers=boundary_headers(**{BOOTSTRAP_HEADER: bootstrap}),
    )
    headers = boundary_headers(**{CAPABILITY_HEADER: capability})

    assert client.get("/openapi.json", headers=headers).status_code == 404
    assert client.get("/docs", headers=headers).status_code == 404
    assert client.get("/redoc", headers=headers).status_code == 404


def test_shutdown_is_protected_and_requests_graceful_server_exit() -> None:
    shutdown_requests: list[bool] = []
    client, bootstrap, capability = make_client(
        shutdown_callback=lambda: shutdown_requests.append(True)
    )
    client.post(
        "/runtime/bootstrap",
        headers=boundary_headers(**{BOOTSTRAP_HEADER: bootstrap}),
    )

    denied = client.post("/runtime/shutdown", headers=boundary_headers())
    assert denied.status_code == 401
    assert shutdown_requests == []

    accepted = client.post(
        "/runtime/shutdown",
        headers=boundary_headers(**{CAPABILITY_HEADER: capability}),
    )
    assert accepted.status_code == 202
    assert accepted.json() == {"status": "stopping"}
    assert shutdown_requests == [True]
