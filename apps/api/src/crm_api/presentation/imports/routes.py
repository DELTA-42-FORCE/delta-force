"""Rotas HTTP autenticadas da importação do acervo legado (#45)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from crm_api.application.imports.import_legacy_archive import (
    ImportLegacyArchiveUseCase,
)
from crm_api.application.imports.preview_legacy_import import (
    PreviewLegacyImportUseCase,
)
from crm_api.domain.imports.entities import LegacyImportPreview, LegacyImportResult
from crm_api.domain.imports.errors import LegacyImportSourceError
from crm_api.presentation.auth.dependencies import CurrentUser
from crm_api.presentation.imports.dependencies import (
    get_import_legacy_archive_use_case,
    get_preview_legacy_import_use_case,
)
from crm_api.presentation.imports.schemas import (
    LegacyImportItemResponse,
    LegacyImportPreviewRequest,
    LegacyImportPreviewResponse,
    LegacyImportRequest,
    LegacyImportResultItemResponse,
    LegacyImportResultResponse,
)

router = APIRouter(prefix="/imports", tags=["imports"])


def _to_response(preview: LegacyImportPreview) -> LegacyImportPreviewResponse:
    return LegacyImportPreviewResponse(
        source_path=preview.source_path,
        summary=preview.summary,
        items=[
            LegacyImportItemResponse(
                relative_path=item.relative_path,
                client_folder_name=item.client_folder_name,
                status=item.status.value,
                media_type=item.media_type.value if item.media_type else None,
                matched_client_id=item.matched_client_id,
            )
            for item in preview.items
        ],
    )


def _to_result_response(result: LegacyImportResult) -> LegacyImportResultResponse:
    return LegacyImportResultResponse(
        source_path=result.source_path,
        summary=result.summary,
        items=[
            LegacyImportResultItemResponse(
                relative_path=item.relative_path,
                client_folder_name=item.client_folder_name,
                outcome=item.outcome.value,
                document_id=item.document_id,
            )
            for item in result.items
        ],
    )


@router.post("/legacy/preview", response_model=LegacyImportPreviewResponse)
async def preview_legacy_import(
    payload: LegacyImportPreviewRequest,
    current_user: CurrentUser,
    use_case: Annotated[
        PreviewLegacyImportUseCase, Depends(get_preview_legacy_import_use_case)
    ],
) -> LegacyImportPreviewResponse:
    """Ensaia a importação da pasta de origem, sem escrever nada, para revisão."""
    try:
        preview = await use_case.execute(source_path=payload.source_path)
    except LegacyImportSourceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from None
    return _to_response(preview)


@router.post("/legacy", response_model=LegacyImportResultResponse)
async def import_legacy_archive(
    payload: LegacyImportRequest,
    current_user: CurrentUser,
    use_case: Annotated[
        ImportLegacyArchiveUseCase, Depends(get_import_legacy_archive_use_case)
    ],
) -> LegacyImportResultResponse:
    """Importa os arquivos elegíveis da origem, copiando, deduplicando e auditando."""
    try:
        result = await use_case.execute(
            actor_user_id=current_user.id, source_path=payload.source_path
        )
    except LegacyImportSourceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from None
    return _to_result_response(result)
