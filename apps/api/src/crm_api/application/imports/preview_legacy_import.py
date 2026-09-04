"""Prévia (sem escrita) da importação do acervo legado de documentos (#45)."""

from dataclasses import dataclass
from uuid import UUID

from crm_api.domain.clients.entities import ClientFolder
from crm_api.domain.clients.repositories import ClientFolderRepository
from crm_api.domain.imports.entities import (
    LegacyImportItem,
    LegacyImportItemStatus,
    LegacyImportPreview,
    LegacyScanEntry,
)
from crm_api.domain.imports.repositories import LegacyArchiveScanner


@dataclass(frozen=True, slots=True)
class PreviewLegacyImportUseCase:
    """Descreve o que a importação faria, casando origem com clientes existentes.

    A prévia não escreve nada: apenas varre a origem, valida o conteúdo de cada
    arquivo e propõe a associação com o cliente já cadastrado de mesmo nome. O
    que não casa de forma única fica de fora, para o proprietário revisar.
    """

    clients: ClientFolderRepository
    scanner: LegacyArchiveScanner

    async def execute(self, *, source_path: str) -> LegacyImportPreview:
        entries = await self.scanner.scan(source_path=source_path)
        matches: dict[str, list[ClientFolder]] = {}
        items: list[LegacyImportItem] = []
        for entry in entries:
            items.append(await self._classify(entry, matches))
        return LegacyImportPreview(source_path=source_path, items=tuple(items))

    async def _classify(
        self, entry: LegacyScanEntry, matches: dict[str, list[ClientFolder]]
    ) -> LegacyImportItem:
        if entry.media_type is None:
            status = (
                LegacyImportItemStatus.UNSUPPORTED_FORMAT
                if entry.reason == "unsupported_format"
                else LegacyImportItemStatus.UNREADABLE
            )
            return self._item(entry, status, matched_client_id=None)

        if entry.client_folder_name is None:
            return self._item(
                entry, LegacyImportItemStatus.CLIENT_NOT_FOUND, matched_client_id=None
            )

        candidates = await self._matches_for(entry.client_folder_name, matches)
        if len(candidates) == 1:
            return self._item(
                entry,
                LegacyImportItemStatus.MATCHED,
                matched_client_id=candidates[0].id,
            )
        if len(candidates) > 1:
            return self._item(
                entry, LegacyImportItemStatus.CLIENT_AMBIGUOUS, matched_client_id=None
            )
        return self._item(
            entry, LegacyImportItemStatus.CLIENT_NOT_FOUND, matched_client_id=None
        )

    async def _matches_for(
        self, folder_name: str, cache: dict[str, list[ClientFolder]]
    ) -> list[ClientFolder]:
        key = folder_name.strip().lower()
        if key not in cache:
            cache[key] = await self.clients.find_by_display_name(
                display_name=folder_name
            )
        return cache[key]

    @staticmethod
    def _item(
        entry: LegacyScanEntry,
        status: LegacyImportItemStatus,
        *,
        matched_client_id: UUID | None,
    ) -> LegacyImportItem:
        return LegacyImportItem(
            relative_path=entry.relative_path,
            client_folder_name=entry.client_folder_name,
            status=status,
            media_type=entry.media_type,
            matched_client_id=matched_client_id,
        )
