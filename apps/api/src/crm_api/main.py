from fastapi import FastAPI, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from crm_api.infrastructure.database import check_database_connection
from crm_api.presentation.auth.routes import router as auth_router
from crm_api.presentation.users.routes import router as users_router

app = FastAPI(title="Delta Force CRM API", version="0.1.0")
app.include_router(auth_router)
app.include_router(users_router)


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
