"""Espera o PostgreSQL local ficar pronto sem depender do shell do sistema."""

import asyncio
import selectors
import sys

from crm_api.infrastructure.database import check_database_connection


async def wait_for_database() -> None:
    last_error: Exception | None = None
    for _ in range(15):
        try:
            await check_database_connection()
            return
        except Exception as error:  # noqa: BLE001 - relata a última falha após retries
            last_error = error
            await asyncio.sleep(2)
    raise RuntimeError("PostgreSQL did not become ready") from last_error


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(
            wait_for_database(),
            loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
        )
    else:
        asyncio.run(wait_for_database())
