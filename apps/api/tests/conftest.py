"""Configuração compartilhada da suíte de testes."""

import asyncio
import sys


if sys.platform == "win32":
    # psycopg async não suporta o ProactorEventLoop padrão do Windows.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
