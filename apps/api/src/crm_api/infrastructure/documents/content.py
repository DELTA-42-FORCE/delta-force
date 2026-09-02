"""Reconhecimento do conteúdo real de documentos PDF e JPEG.

A extensão enviada pelo cliente nunca decide o formato: o tipo vem da assinatura
lida no início do fluxo. As regras de nome ficam em `domain.documents.naming`.
"""

from crm_api.domain.documents.entities import DocumentMediaType
from crm_api.domain.documents.errors import UnsupportedDocumentMediaTypeError

_PDF_SIGNATURE = b"%PDF-"
_PDF_TRAILER = b"%%EOF"
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_JPEG_TRAILER = b"\xff\xd9"

_SIGNATURES: tuple[tuple[bytes, DocumentMediaType], ...] = (
    (_PDF_SIGNATURE, DocumentMediaType.PDF),
    (_JPEG_SIGNATURE, DocumentMediaType.JPEG),
)
_HEAD_WINDOW_BYTES = max(len(signature) for signature, _ in _SIGNATURES)

# A especificação do PDF exige %%EOF no último kilobyte e o JPEG termina com a
# marca EOI. A janela tolera preenchimento final de digitalizadores antigos sem
# deixar de detectar um arquivo truncado.
_TAIL_WINDOW_BYTES = 1024


class DocumentContentInspector:
    """Reconhece o formato pela assinatura e confirma o encerramento do arquivo."""

    __slots__ = ("_head", "_tail", "_byte_size", "_media_type")

    def __init__(self) -> None:
        self._head = bytearray()
        self._tail = bytearray()
        self._byte_size = 0
        self._media_type: DocumentMediaType | None = None

    @property
    def media_type(self) -> DocumentMediaType | None:
        """Formato já reconhecido, quando a assinatura completa foi lida."""
        return self._media_type

    def update(self, chunk: bytes) -> None:
        """Consome um bloco do fluxo, recusando o formato na primeira evidência."""
        if not chunk:
            return

        self._byte_size += len(chunk)
        if self._media_type is None:
            missing = _HEAD_WINDOW_BYTES - len(self._head)
            self._head.extend(chunk[:missing])
            if len(self._head) == _HEAD_WINDOW_BYTES:
                self._media_type = self._detect(bytes(self._head))

        self._tail.extend(chunk)
        if len(self._tail) > _TAIL_WINDOW_BYTES:
            del self._tail[: len(self._tail) - _TAIL_WINDOW_BYTES]

    def finish(self) -> tuple[DocumentMediaType, int]:
        """Conclui a inspeção devolvendo o formato e o tamanho observados."""
        if self._media_type is None:
            raise UnsupportedDocumentMediaTypeError(
                "document content is too short to be a supported format"
            )

        tail = bytes(self._tail)
        if self._media_type is DocumentMediaType.PDF and _PDF_TRAILER not in tail:
            raise UnsupportedDocumentMediaTypeError(
                "PDF content is truncated: the %%EOF marker is missing"
            )
        if self._media_type is DocumentMediaType.JPEG and _JPEG_TRAILER not in tail:
            raise UnsupportedDocumentMediaTypeError(
                "JPEG content is truncated: the end-of-image marker is missing"
            )
        return self._media_type, self._byte_size

    @staticmethod
    def _detect(head: bytes) -> DocumentMediaType:
        for signature, media_type in _SIGNATURES:
            if head.startswith(signature):
                return media_type
        raise UnsupportedDocumentMediaTypeError(
            "document content is neither a PDF nor a JPEG"
        )
