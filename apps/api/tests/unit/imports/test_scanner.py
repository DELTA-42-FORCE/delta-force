"""A varredura classifica os arquivos da origem sem escrever nela (#45)."""

import os
from pathlib import Path

import pytest

from crm_api.domain.documents.entities import DocumentMediaType
from crm_api.domain.imports.errors import LegacyImportSourceError
from crm_api.infrastructure.imports.scanner import FilesystemLegacyArchiveScanner

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x11" * 64 + b"\xff\xd9"

SCANNER = FilesystemLegacyArchiveScanner()


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


async def test_classifies_each_file_by_content_and_client_folder(
    tmp_path: Path,
) -> None:
    root = tmp_path / "acervo"
    _write(root / "Ana Souza" / "contrato.pdf", PDF_BYTES)
    _write(root / "Ana Souza" / "sub" / "rg.jpg", JPEG_BYTES)
    _write(root / "Bruno Lima" / "planilha.xlsx", b"PK\x03\x04zip")
    _write(root / "Bruno Lima" / "quebrado.pdf", PDF_BYTES.replace(b"%%EOF\n", b""))
    _write(root / "solto.pdf", PDF_BYTES)

    entries = {
        entry.relative_path: entry
        for entry in await SCANNER.scan(source_path=str(root))
    }

    assert set(entries) == {
        "Ana Souza/contrato.pdf",
        "Ana Souza/sub/rg.jpg",
        "Bruno Lima/planilha.xlsx",
        "Bruno Lima/quebrado.pdf",
        "solto.pdf",
    }

    contrato = entries["Ana Souza/contrato.pdf"]
    assert contrato.client_folder_name == "Ana Souza"
    assert contrato.media_type is DocumentMediaType.PDF
    assert contrato.reason is None

    rg = entries["Ana Souza/sub/rg.jpg"]
    assert rg.client_folder_name == "Ana Souza"
    assert rg.media_type is DocumentMediaType.JPEG

    # Extensão fora do catálogo nem é lida: entra como formato não suportado.
    planilha = entries["Bruno Lima/planilha.xlsx"]
    assert planilha.media_type is None
    assert planilha.reason == "unsupported_format"

    # PDF truncado (sem %%EOF) é reconhecido como formato inválido.
    quebrado = entries["Bruno Lima/quebrado.pdf"]
    assert quebrado.media_type is None
    assert quebrado.reason == "unsupported_format"

    # Arquivo solto na raiz não pertence a nenhuma pasta de cliente.
    solto = entries["solto.pdf"]
    assert solto.client_folder_name is None
    assert solto.media_type is DocumentMediaType.PDF


async def test_a_jpeg_renamed_as_pdf_is_reported_as_unsupported(tmp_path: Path) -> None:
    root = tmp_path / "acervo"
    _write(root / "Ana Souza" / "disfarcado.pdf", JPEG_BYTES)

    (entry,) = await SCANNER.scan(source_path=str(root))

    assert entry.media_type is None
    assert entry.reason == "unsupported_format"


@pytest.mark.skipif(os.name == "nt", reason="Windows CI may not permit symlinks")
async def test_a_symbolic_link_is_reported_without_reading_its_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "acervo"
    target = tmp_path / "outside.pdf"
    target.write_bytes(PDF_BYTES)
    link = root / "Ana Souza" / "link.pdf"
    link.parent.mkdir(parents=True)
    link.symlink_to(target)

    (entry,) = await SCANNER.scan(source_path=str(root))

    assert entry.relative_path == "Ana Souza/link.pdf"
    assert entry.media_type is None
    assert entry.reason == "unreadable"


async def test_scanning_never_writes_to_the_source(tmp_path: Path) -> None:
    root = tmp_path / "acervo"
    _write(root / "Ana Souza" / "contrato.pdf", PDF_BYTES)
    before = {path: path.stat().st_mtime_ns for path in root.rglob("*")}

    await SCANNER.scan(source_path=str(root))

    after = {path: path.stat().st_mtime_ns for path in root.rglob("*")}
    assert before == after


async def test_a_missing_source_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(LegacyImportSourceError):
        await SCANNER.scan(source_path=str(tmp_path / "nao-existe"))


async def test_a_file_path_as_source_is_rejected(tmp_path: Path) -> None:
    file_path = tmp_path / "arquivo.pdf"
    file_path.write_bytes(PDF_BYTES)

    with pytest.raises(LegacyImportSourceError):
        await SCANNER.scan(source_path=str(file_path))


@pytest.mark.skipif(os.name == "nt", reason="Windows CI may not permit symlinks")
async def test_a_symbolic_link_to_a_source_directory_is_rejected(
    tmp_path: Path,
) -> None:
    source = tmp_path / "real-acervo"
    _write(source / "Ana Souza" / "contrato.pdf", PDF_BYTES)
    link = tmp_path / "linked-acervo"
    link.symlink_to(source, target_is_directory=True)

    with pytest.raises(LegacyImportSourceError):
        await SCANNER.scan(source_path=str(link))
