"""Portas da importação do acervo legado (#45)."""

from collections.abc import AsyncIterator
from typing import Protocol

from crm_api.domain.imports.entities import LegacyScanEntry


class LegacyArchiveScanner(Protocol):
    """Lê a pasta de origem, sem nunca escrever nela: classifica e transmite."""

    async def scan(self, *, source_path: str) -> list[LegacyScanEntry]: ...

    def stream_file(
        self, *, source_path: str, relative_path: str
    ) -> AsyncIterator[bytes]: ...
