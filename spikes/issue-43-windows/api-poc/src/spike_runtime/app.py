"""Minimal FastAPI surface used only by the architecture spike."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from spike_runtime.security import RuntimeAccessDenied, RuntimeGate

BOOTSTRAP_HEADER = "x-runtime-bootstrap"
CAPABILITY_HEADER = "x-runtime-capability"
BOOTSTRAP_PATH = "/runtime/bootstrap"
DEFAULT_TAURI_ORIGIN = "http://tauri.localhost"
_REJECTION_BODY = {"detail": "request rejected"}


def _rejection(
    status_code: int,
    *,
    allowed_origin: str | None = None,
) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if allowed_origin is not None:
        headers["Access-Control-Allow-Origin"] = allowed_origin
        headers["Vary"] = "Origin"
    return JSONResponse(
        status_code=status_code,
        content=_REJECTION_BODY,
        headers=headers,
    )


def create_app(
    gate: RuntimeGate,
    *,
    expected_host: str,
    shutdown_callback: Callable[[], None],
    expected_origin: str = DEFAULT_TAURI_ORIGIN,
) -> FastAPI:
    """Create an API with an exact origin/host boundary and no discovery UI."""

    if not expected_host or not expected_origin:
        raise ValueError("host and origin allowlists must not be empty")

    app = FastAPI(
        title="Delta Force runtime spike",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[expected_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=[CAPABILITY_HEADER],
    )

    @app.middleware("http")
    async def enforce_runtime_boundary(request: Request, call_next):
        if request.headers.get("host") != expected_host:
            return _rejection(400)
        if request.headers.get("origin") != expected_origin:
            return _rejection(403)

        is_bootstrap = request.method == "POST" and request.url.path == BOOTSTRAP_PATH
        # Browser preflight carries no application data and cannot attach the
        # capability. CORS validates its requested method/header exactly.
        is_preflight = request.method == "OPTIONS" and bool(
            request.headers.get("access-control-request-method")
        )
        if (
            not is_bootstrap
            and not is_preflight
            and not gate.authorizes(request.headers.get(CAPABILITY_HEADER))
        ):
            return _rejection(401, allowed_origin=expected_origin)

        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.post(BOOTSTRAP_PATH, include_in_schema=False)
    def bootstrap(request: Request) -> JSONResponse:
        try:
            capability = gate.exchange(request.headers.get(BOOTSTRAP_HEADER))
        except RuntimeAccessDenied:
            return _rejection(401)
        return JSONResponse(
            content={"capability": capability},
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/runtime/probe", include_in_schema=False)
    def runtime_probe() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/runtime/shutdown", status_code=202, include_in_schema=False)
    def runtime_shutdown() -> dict[str, str]:
        shutdown_callback()
        return {"status": "stopping"}

    return app
