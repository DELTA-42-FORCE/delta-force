from fastapi.testclient import TestClient

from crm_api.core.desktop_runtime import (
    DESKTOP_BOOTSTRAP_SECRET_HEADER,
    DESKTOP_CAPABILITY_HEADER,
    DESKTOP_ORIGIN,
    DesktopRuntime,
)
from crm_api.main import create_app

_PORT = 43123
_HOST = f"127.0.0.1:{_PORT}"


def _headers(**extra: str) -> dict[str, str]:
    return {"host": _HOST, "origin": DESKTOP_ORIGIN, **extra}


def test_runtime_bootstrap_secret_is_single_use_and_never_returned_in_error() -> None:
    runtime = DesktopRuntime(bootstrap_secret="synthetic-bootstrap-secret", port=_PORT)

    first_capability = runtime.issue_capability(
        supplied_secret="synthetic-bootstrap-secret",
        host=_HOST,
        origin=DESKTOP_ORIGIN,
    )
    second_capability = runtime.issue_capability(
        supplied_secret="synthetic-bootstrap-secret",
        host=_HOST,
        origin=DESKTOP_ORIGIN,
    )

    assert first_capability is not None
    assert second_capability is None
    assert runtime.accepts_capability(
        supplied_capability=first_capability,
        host=_HOST,
        origin=DESKTOP_ORIGIN,
    )


def test_runtime_rejects_wrong_origin_host_and_capability_from_another_instance() -> (
    None
):
    first = DesktopRuntime(bootstrap_secret="first-secret", port=_PORT)
    second = DesktopRuntime(bootstrap_secret="second-secret", port=_PORT)
    capability = first.issue_capability(
        supplied_secret="first-secret", host=_HOST, origin=DESKTOP_ORIGIN
    )

    assert capability is not None
    assert (
        first.issue_capability(
            supplied_secret="first-secret",
            host="localhost:43123",
            origin=DESKTOP_ORIGIN,
        )
        is None
    )
    assert (
        first.issue_capability(
            supplied_secret="first-secret",
            host=_HOST,
            origin="https://untrusted.example",
        )
        is None
    )
    assert not second.accepts_capability(
        supplied_capability=capability,
        host=_HOST,
        origin=DESKTOP_ORIGIN,
    )


def test_desktop_api_rejects_unbootstrapped_and_untrusted_requests() -> None:
    runtime = DesktopRuntime(bootstrap_secret="bootstrap-secret", port=_PORT)
    client = TestClient(create_app(desktop_runtime=runtime))

    denied = client.get("/health", headers=_headers())
    wrong_origin = client.post(
        "/_desktop/bootstrap",
        headers=_headers(
            **{
                "origin": "https://untrusted.example",
                DESKTOP_BOOTSTRAP_SECRET_HEADER: "bootstrap-secret",
            }
        ),
    )

    assert denied.status_code == 403
    assert wrong_origin.status_code == 403
    assert "bootstrap-secret" not in wrong_origin.text


def test_desktop_api_only_accepts_the_capability_issued_to_its_instance() -> None:
    runtime = DesktopRuntime(bootstrap_secret="bootstrap-secret", port=_PORT)
    client = TestClient(create_app(desktop_runtime=runtime))

    bootstrap = client.post(
        "/_desktop/bootstrap",
        headers=_headers(**{DESKTOP_BOOTSTRAP_SECRET_HEADER: "bootstrap-secret"}),
    )
    capability = bootstrap.json()["capability"]
    accepted = client.get(
        "/health",
        headers=_headers(**{DESKTOP_CAPABILITY_HEADER: capability}),
    )
    replay = client.post(
        "/_desktop/bootstrap",
        headers=_headers(**{DESKTOP_BOOTSTRAP_SECRET_HEADER: "bootstrap-secret"}),
    )

    assert bootstrap.status_code == 200
    assert accepted.status_code == 200
    assert replay.status_code == 403
