"""Entidade da pasta digital flexível de um cliente."""

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ClientFolderCursor:
    """Posição exclusiva e estável na ordenação alfabética do diretório."""

    display_name: str
    id: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.display_name, str) or not self.display_name:
            raise ValueError("client folder cursor display_name must not be blank")
        if not isinstance(self.id, UUID):
            raise ValueError("client folder cursor id must be a UUID")


@dataclass(frozen=True, slots=True)
class ClientFolder:
    """Pasta de um cliente, sem catálogo rígido de campos ou documentos."""

    id: UUID
    display_name: str
    profile_data: Mapping[str, str]
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise ValueError("client folder id must be a UUID")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("client folder display_name must not be blank")
        if not isinstance(self.profile_data, Mapping) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in self.profile_data.items()
        ):
            raise ValueError("client folder profile_data must map strings to strings")
        object.__setattr__(
            self, "profile_data", MappingProxyType(dict(self.profile_data))
        )
