"""Endpoint interno que entrega a capability ao supervisor Tauri."""

from fastapi import APIRouter, HTTPException, Request, status

from crm_api.core.desktop_runtime import DESKTOP_BOOTSTRAP_SECRET_HEADER, DesktopRuntime

router = APIRouter(include_in_schema=False)


def _runtime(request: Request) -> DesktopRuntime:
    runtime = getattr(request.app.state, "desktop_runtime", None)
    if not isinstance(runtime, DesktopRuntime):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return runtime


@router.post("/_desktop/bootstrap")
async def bootstrap_desktop_capability(request: Request) -> dict[str, str]:
    """Aceita o segredo uma única vez, somente do supervisor local permitido."""
    capability = _runtime(request).issue_capability(
        supplied_secret=request.headers.get(DESKTOP_BOOTSTRAP_SECRET_HEADER),
        host=request.headers.get("host"),
        origin=request.headers.get("origin"),
    )
    if capability is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="desktop bootstrap denied",
        )
    return {"capability": capability}
