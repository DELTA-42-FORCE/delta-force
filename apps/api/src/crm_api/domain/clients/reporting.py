"""Projeção da pasta de cliente para geração da ficha cadastral (#34)."""

from dataclasses import dataclass
from typing import Protocol

from crm_api.domain.clients.entities import ClientFolder


@dataclass(frozen=True, slots=True)
class ClientProfileField:
    """Um campo opcional disponível na pasta, já pronto para exibição."""

    label: str
    value: str


@dataclass(frozen=True, slots=True)
class ClientProfileDocument:
    """Conteúdo da ficha: nome de identificação e os campos que existirem.

    A pasta é flexível e não tem catálogo obrigatório: a ficha apresenta apenas
    os campos preenchidos, e a ausência de qualquer um nunca impede a geração.
    """

    heading: str
    display_name: str
    fields: tuple[ClientProfileField, ...]

    @classmethod
    def from_folder(
        cls, client: ClientFolder, *, heading: str = "Ficha cadastral"
    ) -> "ClientProfileDocument":
        """Monta a ficha a partir da pasta, ignorando campos em branco."""
        fields = tuple(
            ClientProfileField(label=key.strip(), value=value.strip())
            for key, value in client.profile_data.items()
            if key.strip() and value.strip()
        )
        return cls(
            heading=heading,
            display_name=client.display_name.strip(),
            fields=fields,
        )


class ClientProfilePdfRenderer(Protocol):
    """Porta de renderização da ficha em PDF, sem acoplar o caso de uso ao formato."""

    def render(self, document: ClientProfileDocument) -> bytes: ...
