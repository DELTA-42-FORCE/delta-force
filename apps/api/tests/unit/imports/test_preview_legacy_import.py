"""A prévia casa origem com clientes existentes e classifica cada arquivo (#45)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from crm_api.application.imports.preview_legacy_import import (
    PreviewLegacyImportUseCase,
)
from crm_api.domain.clients.entities import ClientFolder
from crm_api.domain.documents.entities import DocumentMediaType
from crm_api.domain.imports.entities import LegacyImportItemStatus, LegacyScanEntry


@dataclass
class _MemoryClientRepository:
    folders: list[ClientFolder] = field(default_factory=list)
    calls: int = 0

    def add(self, display_name: str) -> ClientFolder:
        folder = ClientFolder(
            id=uuid4(),
            display_name=display_name,
            profile_data={},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.folders.append(folder)
        return folder

    async def find_by_display_name(self, *, display_name: str) -> list[ClientFolder]:
        self.calls += 1
        target = display_name.strip().lower()
        return [
            folder
            for folder in self.folders
            if folder.display_name.strip().lower() == target
        ]


@dataclass
class _StubScanner:
    entries: list[LegacyScanEntry]

    async def scan(self, *, source_path: str) -> list[LegacyScanEntry]:
        assert source_path == "C:/acervo"
        return list(self.entries)


def _ok(client: str | None, path: str) -> LegacyScanEntry:
    return LegacyScanEntry(
        client_folder_name=client,
        relative_path=path,
        media_type=DocumentMediaType.PDF,
        reason=None,
    )


def _bad(client: str | None, path: str, reason: str) -> LegacyScanEntry:
    return LegacyScanEntry(
        client_folder_name=client,
        relative_path=path,
        media_type=None,
        reason=reason,
    )


async def test_classifies_every_status_and_summarizes() -> None:
    repository = _MemoryClientRepository()
    repository.add("Ana Souza")
    repository.add("Carlos Dias")
    repository.add("Carlos Dias")  # homônimo: associação ambígua

    scanner = _StubScanner(
        [
            _ok("Ana Souza", "Ana Souza/contrato.pdf"),
            _ok("Ana Souza", "Ana Souza/rg.pdf"),
            _ok("Desconhecido", "Desconhecido/x.pdf"),
            _ok("Carlos Dias", "Carlos Dias/y.pdf"),
            _ok(None, "solto.pdf"),
            _bad("Ana Souza", "Ana Souza/planilha.xlsx", "unsupported_format"),
            _bad("Ana Souza", "Ana Souza/ilegivel.pdf", "unreadable"),
        ]
    )
    use_case = PreviewLegacyImportUseCase(clients=repository, scanner=scanner)

    preview = await use_case.execute(source_path="C:/acervo")

    by_path = {item.relative_path: item for item in preview.items}
    ana = repository.folders[0]
    assert by_path["Ana Souza/contrato.pdf"].status is LegacyImportItemStatus.MATCHED
    assert by_path["Ana Souza/contrato.pdf"].matched_client_id == ana.id
    assert (
        by_path["Desconhecido/x.pdf"].status is LegacyImportItemStatus.CLIENT_NOT_FOUND
    )
    assert (
        by_path["Carlos Dias/y.pdf"].status is LegacyImportItemStatus.CLIENT_AMBIGUOUS
    )
    assert by_path["Carlos Dias/y.pdf"].matched_client_id is None
    assert by_path["solto.pdf"].status is LegacyImportItemStatus.CLIENT_NOT_FOUND
    assert (
        by_path["Ana Souza/planilha.xlsx"].status
        is LegacyImportItemStatus.UNSUPPORTED_FORMAT
    )
    assert by_path["Ana Souza/ilegivel.pdf"].status is LegacyImportItemStatus.UNREADABLE

    assert preview.summary == {
        "matched": 2,
        "client_not_found": 2,
        "client_ambiguous": 1,
        "unsupported_format": 1,
        "unreadable": 1,
        "total": 7,
    }


async def test_repeated_folder_names_are_matched_only_once() -> None:
    repository = _MemoryClientRepository()
    repository.add("Ana Souza")
    scanner = _StubScanner(
        [
            _ok("Ana Souza", "Ana Souza/a.pdf"),
            _ok("Ana Souza", "Ana Souza/b.pdf"),
            _ok("Ana Souza", "Ana Souza/c.pdf"),
        ]
    )
    use_case = PreviewLegacyImportUseCase(clients=repository, scanner=scanner)

    preview = await use_case.execute(source_path="C:/acervo")

    assert all(item.status is LegacyImportItemStatus.MATCHED for item in preview.items)
    # A busca por nome é cacheada: uma pasta repetida não consulta o banco de novo.
    assert repository.calls == 1


async def test_invalid_content_is_not_matched_to_a_client() -> None:
    repository = _MemoryClientRepository()
    repository.add("Ana Souza")
    scanner = _StubScanner(
        [_bad("Ana Souza", "Ana Souza/planilha.xlsx", "unsupported_format")]
    )
    use_case = PreviewLegacyImportUseCase(clients=repository, scanner=scanner)

    preview = await use_case.execute(source_path="C:/acervo")

    assert preview.items[0].matched_client_id is None
    # Conteúdo inválido nem chega a consultar clientes.
    assert repository.calls == 0
