"""Validação do nome declarado e do conteúdo real de documentos PDF e JPEG.

A extensão enviada pelo cliente nunca decide o formato: o tipo vem da assinatura
lida no início do fluxo e a extensão só é aceita se concordar com ele.
"""

from pathlib import PurePosixPath, PureWindowsPath

from crm_api.domain.documents.entities import DocumentMediaType
from crm_api.domain.documents.errors import (
    InvalidDocumentNameError,
    UnsupportedDocumentMediaTypeError,
)

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

_MAX_FILENAME_LENGTH = 255
_FORBIDDEN_FILENAME_CHARACTERS = frozenset('<>:"/\\|?*')
_WINDOWS_RESERVED_STEMS = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{digit}" for digit in range(1, 10)}
    | {f"lpt{digit}" for digit in range(1, 10)}
)
_ACCEPTED_EXTENSIONS = frozenset(
    extension
    for media_type in DocumentMediaType
    for extension in media_type.accepted_extensions
)


def normalize_document_filename(value: str) -> str:
    """Aceita apenas um nome de arquivo simples, seguro no Windows e com extensão."""
    if not isinstance(value, str):
        raise InvalidDocumentNameError("document filename must be a string")

    candidate = value.strip()
    if not candidate:
        raise InvalidDocumentNameError("document filename must not be blank")
    if len(candidate) > _MAX_FILENAME_LENGTH:
        raise InvalidDocumentNameError(
            f"document filename must not exceed {_MAX_FILENAME_LENGTH} characters"
        )
    if any(character in _FORBIDDEN_FILENAME_CHARACTERS for character in candidate):
        raise InvalidDocumentNameError("document filename contains a forbidden symbol")
    if any(ord(character) < 32 or ord(character) == 127 for character in candidate):
        raise InvalidDocumentNameError("document filename contains a control character")

    # Impede que um caminho relativo, absoluto ou com fluxo alternativo do NTFS
    # atravesse a árvore privada mesmo que passe pelos filtros anteriores.
    if (
        PurePosixPath(candidate).name != candidate
        or PureWindowsPath(candidate).name != candidate
    ):
        raise InvalidDocumentNameError("document filename must not contain a path")
    if candidate.endswith((".", " ")):
        raise InvalidDocumentNameError("document filename must not end with . or space")

    stem, _, extension = candidate.rpartition(".")
    if not stem:
        raise InvalidDocumentNameError("document filename needs a name and extension")
    if stem.split(".")[0].lower() in _WINDOWS_RESERVED_STEMS:
        raise InvalidDocumentNameError("document filename uses a reserved device name")
    if f".{extension.lower()}" not in _ACCEPTED_EXTENSIONS:
        raise InvalidDocumentNameError(
            "document filename must be a .pdf, .jpg or .jpeg"
        )
    return candidate


def assert_extension_matches(*, filename: str, media_type: DocumentMediaType) -> None:
    """Recusa um nome cuja extensão contradiga o conteúdo detectado."""
    extension = f".{filename.rpartition('.')[2].lower()}"
    if extension not in media_type.accepted_extensions:
        raise UnsupportedDocumentMediaTypeError(
            "document extension does not match the detected content"
        )


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
