"""Entidades da prévia de importação do acervo legado (#45).

A prévia é sempre um ensaio sem escrita: descreve o que uma importação faria,
para o proprietário revisar antes de confirmar. A regra de associação combina a
pasta de origem — uma pasta por cliente, cujo nome é o nome do cliente — com as
pastas de cliente já cadastradas; o que não casa de forma única fica de fora.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from crm_api.domain.documents.entities import DocumentMediaType


class LegacyImportItemStatus(StrEnum):
    """Situação de um arquivo de origem na prévia da importação."""

    MATCHED = "matched"
    CLIENT_NOT_FOUND = "client_not_found"
    CLIENT_AMBIGUOUS = "client_ambiguous"
    UNSUPPORTED_FORMAT = "unsupported_format"
    UNREADABLE = "unreadable"


@dataclass(frozen=True, slots=True)
class LegacyScanEntry:
    """Um arquivo encontrado na origem, já classificado quanto ao conteúdo.

    `client_folder_name` é o nome da pasta de primeiro nível sob a raiz; é `None`
    quando o arquivo está solto na raiz, fora de qualquer pasta de cliente.
    `media_type` só é preenchido quando o conteúdo é um PDF ou JPEG íntegro.
    """

    client_folder_name: str | None
    relative_path: str
    media_type: DocumentMediaType | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class LegacyImportItem:
    """Resultado da prévia para um arquivo: situação e cliente sugerido."""

    relative_path: str
    client_folder_name: str | None
    status: LegacyImportItemStatus
    media_type: DocumentMediaType | None
    matched_client_id: UUID | None


@dataclass(frozen=True, slots=True)
class LegacyImportPreview:
    """Ensaio completo da importação, com os itens e a contagem por situação."""

    source_path: str
    items: tuple[LegacyImportItem, ...]

    @property
    def summary(self) -> dict[str, int]:
        """Contagem por situação, incluindo o total, para a revisão do proprietário."""
        counts = {status.value: 0 for status in LegacyImportItemStatus}
        for item in self.items:
            counts[item.status.value] += 1
        counts["total"] = len(self.items)
        return counts
