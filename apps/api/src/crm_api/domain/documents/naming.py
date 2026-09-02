"""Regras de nome de documento, válidas para o arquivo e para os metadados.

Ficam no domínio porque o caso de uso precisa normalizar uma única vez e passar
exatamente o mesmo nome ao armazenamento e ao repositório: um nome aceito para
gravar o arquivo não pode divergir do nome que será exibido e consultado.
"""

from pathlib import PurePosixPath, PureWindowsPath

from crm_api.domain.documents.entities import DocumentMediaType
from crm_api.domain.documents.errors import (
    InvalidDocumentNameError,
    UnsupportedDocumentMediaTypeError,
)

MAX_FILENAME_LENGTH = 255
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
    """Aceita apenas um nome de arquivo simples, seguro no Windows e com extensão.

    É idempotente: aplicar de novo sobre o resultado devolve o mesmo nome.
    """
    if not isinstance(value, str):
        raise InvalidDocumentNameError("document filename must be a string")

    candidate = value.strip()
    if not candidate:
        raise InvalidDocumentNameError("document filename must not be blank")
    if len(candidate) > MAX_FILENAME_LENGTH:
        raise InvalidDocumentNameError(
            f"document filename must not exceed {MAX_FILENAME_LENGTH} characters"
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
