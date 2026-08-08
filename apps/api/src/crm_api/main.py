from fastapi import FastAPI

app = FastAPI(title="Delta Force CRM API", version="0.1.0")


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Expõe um sinal simples de disponibilidade para desenvolvimento e CI."""
    return {"status": "ok"}
