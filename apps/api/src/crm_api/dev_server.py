"""Sobe a API localmente sem recarregamento automático.

O psycopg em modo assíncrono não roda sob o ``ProactorEventLoop`` que o
Windows usa por padrão, e o uvicorn força esse loop quando o recarregamento
automático em subprocesso está desligado. Este script fixa a policy correta
antes de entregar o controle ao uvicorn. Sem ``--reload``: reinicie o
processo manualmente após mudanças de código.
"""

import asyncio
import sys


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    import uvicorn

    uvicorn.run("crm_api.main:app", host="127.0.0.1", port=8000, loop="none")


if __name__ == "__main__":
    main()
