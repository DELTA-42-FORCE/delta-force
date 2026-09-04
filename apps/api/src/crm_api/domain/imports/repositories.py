"""Portas da importação do acervo legado (#45)."""

from typing import Protocol

from crm_api.domain.imports.entities import LegacyScanEntry


class LegacyArchiveScanner(Protocol):
    """Varre a pasta de origem e classifica cada arquivo, sem nunca escrever nela."""

    async def scan(self, *, source_path: str) -> list[LegacyScanEntry]: ...
