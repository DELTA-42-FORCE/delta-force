"""Configuração compartilhada da suíte de testes."""

import asyncio
import os
import sys


# A suíte unitária importa a aplicação durante a coleta, mas não abre conexão.
# A integração substitui esta URL pelo banco descartável criado pelo runner.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://test:test@localhost:5432/delta_force_test",
)


if sys.platform == "win32":
    # psycopg async não suporta o ProactorEventLoop padrão do Windows.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
