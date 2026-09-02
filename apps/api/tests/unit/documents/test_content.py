import pytest

from crm_api.domain.documents.entities import DocumentMediaType
from crm_api.domain.documents.errors import (
    InvalidDocumentNameError,
    UnsupportedDocumentMediaTypeError,
)
from crm_api.infrastructure.documents.content import (
    DocumentContentInspector,
    assert_extension_matches,
    normalize_document_filename,
)

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x11" * 64 + b"\xff\xd9"


def _inspect(payload: bytes, *, chunk_size: int = 8) -> tuple[DocumentMediaType, int]:
    inspector = DocumentContentInspector()
    for start in range(0, len(payload), chunk_size):
        end = start + chunk_size
        inspector.update(payload[start:end])
    return inspector.finish()


def test_accepts_a_simple_pdf_name() -> None:
    assert normalize_document_filename("  contrato assinado.pdf  ") == (
        "contrato assinado.pdf"
    )


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


def test_detects_a_pdf_from_its_signature_and_trailer() -> None:
    assert _inspect(PDF_BYTES) == (DocumentMediaType.PDF, len(PDF_BYTES))


def test_detects_a_jpeg_from_its_signature_and_end_of_image_marker() -> None:
    assert _inspect(JPEG_BYTES) == (DocumentMediaType.JPEG, len(JPEG_BYTES))


def test_rejects_content_that_is_neither_pdf_nor_jpeg() -> None:
    with pytest.raises(UnsupportedDocumentMediaTypeError, match="neither a PDF"):
        _inspect(b"PK\x03\x04arquivo compactado")


def test_rejects_content_shorter_than_any_signature() -> None:
    with pytest.raises(UnsupportedDocumentMediaTypeError, match="too short"):
        _inspect(b"%PD")


def test_rejects_a_truncated_pdf_without_the_eof_marker() -> None:
    with pytest.raises(UnsupportedDocumentMediaTypeError, match="truncated"):
        _inspect(PDF_BYTES.replace(b"%%EOF\n", b""))


def test_rejects_a_truncated_jpeg_without_the_end_of_image_marker() -> None:
    with pytest.raises(UnsupportedDocumentMediaTypeError, match="truncated"):
        _inspect(JPEG_BYTES[:-2])


def test_rejects_a_pdf_whose_eof_marker_left_the_tail_window() -> None:
    padded = PDF_BYTES + b"\x00" * 2048
    with pytest.raises(UnsupportedDocumentMediaTypeError, match="truncated"):
        _inspect(padded, chunk_size=512)


def test_recognizes_the_format_before_the_stream_ends() -> None:
    inspector = DocumentContentInspector()
    inspector.update(PDF_BYTES[:8])

    assert inspector.media_type is DocumentMediaType.PDF


def test_rejects_a_renamed_jpeg_declared_as_pdf() -> None:
    with pytest.raises(UnsupportedDocumentMediaTypeError, match="does not match"):
        assert_extension_matches(
            filename="disfarcado.pdf", media_type=DocumentMediaType.JPEG
        )


@pytest.mark.parametrize("filename", ["foto.jpg", "foto.JPEG"])
def test_accepts_both_jpeg_extensions_for_jpeg_content(filename: str) -> None:
    assert_extension_matches(filename=filename, media_type=DocumentMediaType.JPEG)
