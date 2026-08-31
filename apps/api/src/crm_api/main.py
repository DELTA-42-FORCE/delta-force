from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from crm_api.core.config import get_settings
from crm_api.core.desktop_runtime import DesktopRuntime
from crm_api.infrastructure.database import check_database_connection
from crm_api.presentation.audit.routes import router as audit_router
from crm_api.presentation.auth.routes import router as auth_router
from crm_api.presentation.desktop.routes import router as desktop_router
from crm_api.presentation.desktop.security import DesktopCapabilityMiddleware


def create_app(desktop_runtime: DesktopRuntime | None = None) -> FastAPI:
    """Cria a API para desenvolvimento HTTP ou para o shell desktop fechado."""
    app = FastAPI(
        title="Delta Force CRM API",
        version="0.1.0",
        docs_url=None if desktop_runtime is not None else "/docs",
        redoc_url=None if desktop_runtime is not None else "/redoc",
        openapi_url=None if desktop_runtime is not None else "/openapi.json",
    )
    app.state.desktop_runtime = desktop_runtime
    app.add_middleware(DesktopCapabilityMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=(
            [desktop_runtime.origin]
            if desktop_runtime is not None
            else get_settings().cors_allowed_origins_list
        ),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Delta-Desktop-Capability"],
    )
    app.include_router(desktop_router)
    app.include_router(auth_router)
    app.include_router(audit_router)

    @app.get("/health", tags=["health"])
    def health_check() -> dict[str, str]:
        """Expõe um sinal simples de disponibilidade para desenvolvimento e CI."""
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def readiness_check() -> dict[str, str]:
        """Confirma que a API consegue se conectar ao banco configurado."""
        try:
            await check_database_connection()
        except (SQLAlchemyError, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="database unavailable",
            ) from None

        return {"status": "ok", "database": "ok"}

    return app


app = create_app()
