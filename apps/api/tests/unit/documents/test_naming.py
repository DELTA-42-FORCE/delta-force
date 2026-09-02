import pytest

from crm_api.domain.documents.entities import DocumentMediaType
from crm_api.domain.documents.errors import (
    InvalidDocumentNameError,
    UnsupportedDocumentMediaTypeError,
)
from crm_api.domain.documents.naming import (
    assert_extension_matches,
    normalize_document_filename,
)


def test_trims_the_borders_of_a_declared_name() -> None:
    assert normalize_document_filename("  contrato assinado.pdf  ") == (
        "contrato assinado.pdf"
    )


def test_normalization_is_idempotent() -> None:
    once = normalize_document_filename("  contrato.pdf ")

    assert normalize_document_filename(once) == once


@pytest.mark.parametrize("filename", ["foto.jpg", "foto.JPEG", "digitalizado.Pdf"])
def test_accepts_every_supported_extension_regardless_of_case(filename: str) -> None:
    assert normalize_document_filename(filename) == filename


@pytest.mark.parametrize(
    "filename",
    [
        "",
        "   ",
        "sem-extensao",
        ".pdf",
        "planilha.xlsx",
        "documento.pdf.exe",
        "../fora-da-arvore.pdf",
        "subpasta/arquivo.pdf",
        "subpasta\\arquivo.pdf",
        "C:\\Windows\\system32.pdf",
        "fluxo.pdf:oculto",
        "nome\x00nulo.pdf",
        "quebra\nlinha.pdf",
        "termina-com-ponto.pdf.",
        "CON.pdf",
        "lpt1.jpg",
        f"{'n' * 260}.pdf",
    ],
)
def test_rejects_an_unsafe_or_unsupported_name(filename: str) -> None:
    with pytest.raises(InvalidDocumentNameError):
        normalize_document_filename(filename)


def test_rejects_a_renamed_jpeg_declared_as_pdf() -> None:
    with pytest.raises(UnsupportedDocumentMediaTypeError, match="does not match"):
        assert_extension_matches(
            filename="disfarcado.pdf", media_type=DocumentMediaType.JPEG
        )


@pytest.mark.parametrize("filename", ["foto.jpg", "foto.JPEG"])
def test_accepts_both_jpeg_extensions_for_jpeg_content(filename: str) -> None:
    assert_extension_matches(filename=filename, media_type=DocumentMediaType.JPEG)
