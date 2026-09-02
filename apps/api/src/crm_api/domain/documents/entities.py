"""Entidades do documento privado; o binário nunca entra no banco."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class DocumentMediaType(StrEnum):
    """Catálogo fechado dos formatos aceitos pela decisão do cliente."""

    PDF = "application/pdf"
    JPEG = "image/jpeg"

    @property
    def canonical_extension(self) -> str:
        """Extensão usada na árvore privada, derivada do conteúdo real."""
        return _CANONICAL_EXTENSIONS[self]

    @property
    def accepted_extensions(self) -> frozenset[str]:
        """Extensões que o nome declarado pode usar para este conteúdo."""
        return _ACCEPTED_EXTENSIONS[self]


_CANONICAL_EXTENSIONS = {
    DocumentMediaType.PDF: ".pdf",
    DocumentMediaType.JPEG: ".jpg",
}

_ACCEPTED_EXTENSIONS = {
    DocumentMediaType.PDF: frozenset({".pdf"}),
    DocumentMediaType.JPEG: frozenset({".jpg", ".jpeg"}),
}


@dataclass(frozen=True, slots=True)
class StoredContent:
    """Resultado da gravação já publicada na árvore privada."""

    storage_key: str
    media_type: DocumentMediaType
    byte_size: int
    checksum_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.storage_key, str) or not self.storage_key:
            raise ValueError("stored content storage_key must not be blank")
        if not isinstance(self.media_type, DocumentMediaType):
            raise ValueError("stored content media_type is invalid")
        if not isinstance(self.byte_size, int) or self.byte_size <= 0:
            raise ValueError("stored content byte_size must be positive")
        if len(self.checksum_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.checksum_sha256
        ):
            raise ValueError("stored content checksum must be a sha256 hex digest")


@dataclass(frozen=True, slots=True)
class StoredDocument:
    """Metadados persistentes que apontam para o arquivo na área privada."""

    id: UUID
    client_folder_id: UUID
    original_filename: str
    storage_key: str
    media_type: DocumentMediaType
    byte_size: int
    checksum_sha256: str
    stored_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise ValueError("document id must be a UUID")
        if not isinstance(self.client_folder_id, UUID):
            raise ValueError("document client_folder_id must be a UUID")
        if not isinstance(self.original_filename, str) or not self.original_filename:
            raise ValueError("document original_filename must not be blank")
        if not isinstance(self.storage_key, str) or not self.storage_key:
            raise ValueError("document storage_key must not be blank")
        if not isinstance(self.media_type, DocumentMediaType):
            raise ValueError("document media_type is invalid")
        if not isinstance(self.byte_size, int) or self.byte_size <= 0:
            raise ValueError("document byte_size must be positive")
        if self.stored_at.tzinfo is None or self.stored_at.utcoffset() is None:
            raise ValueError("document stored_at must include a timezone")
