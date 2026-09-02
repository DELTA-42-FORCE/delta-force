import pytest

from crm_api.domain.documents.entities import DocumentMediaType
from crm_api.domain.documents.errors import UnsupportedDocumentMediaTypeError
from crm_api.infrastructure.documents.content import DocumentContentInspector

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x11" * 64 + b"\xff\xd9"


def _inspect(payload: bytes, *, chunk_size: int = 8) -> tuple[DocumentMediaType, int]:
    inspector = DocumentContentInspector()
    for start in range(0, len(payload), chunk_size):
        end = start + chunk_size
        inspector.update(payload[start:end])
    return inspector.finish()


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
