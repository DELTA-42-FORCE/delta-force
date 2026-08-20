"""Servidor de desenvolvimento compatível com o loop assíncrono do Windows."""

import asyncio
import sys


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    import uvicorn

    uvicorn.run("crm_api.main:app", host="127.0.0.1", port=8000, loop="none")


if __name__ == "__main__":
    main()
