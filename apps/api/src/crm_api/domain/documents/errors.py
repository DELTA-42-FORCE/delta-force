"""Erros de domínio do armazenamento privado de documentos."""


class DocumentStorageError(Exception):
    """Falha ao gravar ou publicar um documento na área privada."""


class InvalidDocumentNameError(DocumentStorageError):
    """O nome declarado é vazio, contém caminho ou é inválido no Windows."""


class UnsupportedDocumentMediaTypeError(DocumentStorageError):
    """O conteúdo não é um PDF ou JPEG íntegro, ou contradiz o nome declarado."""


class InsufficientStorageError(DocumentStorageError):
    """O disco não tem capacidade livre suficiente para concluir a gravação."""
