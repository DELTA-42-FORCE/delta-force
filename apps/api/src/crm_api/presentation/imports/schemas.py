"""Esquemas HTTP da prévia de importação do acervo legado (#45)."""

from uuid import UUID

from pydantic import BaseModel, Field


class LegacyImportPreviewRequest(BaseModel):
    """Pasta de origem a ser inspecionada, sem qualquer escrita."""

    source_path: str = Field(min_length=1)


class LegacyImportItemResponse(BaseModel):
    """Situação de um arquivo da origem e o cliente sugerido, quando houver."""

    relative_path: str
    client_folder_name: str | None
    status: str
    media_type: str | None
    matched_client_id: UUID | None


class LegacyImportPreviewResponse(BaseModel):
    """Ensaio completo: contagem por situação e a lista revisável de arquivos."""

    source_path: str
    summary: dict[str, int]
    items: list[LegacyImportItemResponse]


class LegacyImportRequest(BaseModel):
    """Pasta de origem cujos arquivos elegíveis serão importados."""

    source_path: str = Field(min_length=1)


class LegacyImportResultItemResponse(BaseModel):
    """Desfecho de um arquivo e o documento criado, quando houver."""

    relative_path: str
    client_folder_name: str | None
    outcome: str
    document_id: UUID | None


class LegacyImportResultResponse(BaseModel):
    """Relatório da execução: contagem por desfecho e a lista de arquivos."""

    source_path: str
    summary: dict[str, int]
    items: list[LegacyImportResultItemResponse]
