"""Filtro de requests do WebView no runtime desktop."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from crm_api.core.desktop_runtime import DESKTOP_CAPABILITY_HEADER, DesktopRuntime

_BOOTSTRAP_PATH = "/_desktop/bootstrap"


class DesktopCapabilityMiddleware(BaseHTTPMiddleware):
    """Exige capability e origem exata para cada chamada normal da janela."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        runtime = getattr(request.app.state, "desktop_runtime", None)
        if not isinstance(runtime, DesktopRuntime):
            return await call_next(request)

        if request.method == "OPTIONS" or request.url.path == _BOOTSTRAP_PATH:
            return await call_next(request)

        if runtime.accepts_capability(
            supplied_capability=request.headers.get(DESKTOP_CAPABILITY_HEADER),
            host=request.headers.get("host"),
            origin=request.headers.get("origin"),
        ):
            return await call_next(request)

        return JSONResponse(
            status_code=403,
            content={"detail": "desktop capability denied"},
        )
