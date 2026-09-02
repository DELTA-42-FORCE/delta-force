"""Rotas HTTP autenticadas de anexo, consulta e exportação de documentos."""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi import status
from fastapi.responses import StreamingResponse

from crm_api.application.documents.export_client_document import (
    ExportClientDocumentUseCase,
)
from crm_api.application.documents.get_client_document import (
    GetClientDocumentUseCase,
)
from crm_api.application.documents.list_client_documents import (
    ListClientDocumentsUseCase,
)
from crm_api.application.documents.store_document import StoreDocumentUseCase
from crm_api.domain.clients.errors import ClientFolderNotFoundError
from crm_api.domain.documents.entities import DocumentCursor, StoredDocument
from crm_api.domain.documents.errors import (
    DocumentContentUnavailableError,
    DocumentNotFoundError,
    DocumentStorageError,
    InsufficientStorageError,
    InvalidDocumentNameError,
    UnsupportedDocumentMediaTypeError,
)
from crm_api.presentation.auth.dependencies import CurrentUser
from crm_api.presentation.documents.dependencies import (
    get_export_client_document_use_case,
    get_get_client_document_use_case,
    get_list_client_documents_use_case,
    get_store_document_use_case,
)
from crm_api.presentation.documents.schemas import (
    DocumentCursorResponse,
    DocumentListResponse,
    DocumentResponse,
)

router = APIRouter(prefix="/clients", tags=["documents"])

_CLIENT_NOT_FOUND_DETAIL = "client folder not found"
_DOCUMENT_NOT_FOUND_DETAIL = "document not found"
_UPLOAD_CHUNK_BYTES = 1024 * 1024


def _to_response(document: StoredDocument) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        client_folder_id=document.client_folder_id,
        original_filename=document.original_filename,
        media_type=document.media_type.value,
        byte_size=document.byte_size,
        checksum_sha256=document.checksum_sha256,
        stored_at=document.stored_at,
        title=document.title,
        category=document.category,
        notes=document.notes,
    )


async def _upload_chunks(upload: UploadFile) -> AsyncIterator[bytes]:
    """Entrega o corpo em blocos: o arquivo nunca é materializado em memória."""
    while True:
        chunk = await upload.read(_UPLOAD_CHUNK_BYTES)
        if not chunk:
            return
        yield chunk


def _content_disposition(filename: str) -> str:
    """Força download de cópia e mantém o nome legível em qualquer navegador."""
    ascii_fallback = filename.encode("ascii", "replace").decode("ascii")
    return (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{quote(filename, safe='')}"
    )


@router.post(
    "/{client_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def attach_document(
    client_id: UUID,
    current_user: CurrentUser,
    use_case: Annotated[StoreDocumentUseCase, Depends(get_store_document_use_case)],
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
    category: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
) -> DocumentResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="o arquivo enviado precisa ter um nome",
        )

    try:
        document = await use_case.execute(
            actor_user_id=current_user.id,
            client_folder_id=client_id,
            original_filename=file.filename,
            chunks=_upload_chunks(file),
            title=title,
            category=category,
            notes=notes,
        )
    except ClientFolderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_CLIENT_NOT_FOUND_DETAIL
        ) from None
    except InvalidDocumentNameError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from None
    except UnsupportedDocumentMediaTypeError as error:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(error)
        ) from None
    except InsufficientStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE, detail=str(error)
        ) from None
    except DocumentStorageError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="não foi possível armazenar o documento",
        ) from None
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from None
    return _to_response(document)


@router.get("/{client_id}/documents", response_model=DocumentListResponse)
async def list_client_documents(
    client_id: UUID,
    current_user: CurrentUser,
    use_case: Annotated[
        ListClientDocumentsUseCase, Depends(get_list_client_documents_use_case)
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before_stored_at: Annotated[datetime | None, Query()] = None,
    before_id: Annotated[UUID | None, Query()] = None,
) -> DocumentListResponse:
    if (before_stored_at is None) != (before_id is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="before_stored_at and before_id must be provided together",
        )
    try:
        cursor = (
            DocumentCursor(stored_at=before_stored_at, id=before_id)
            if before_stored_at is not None and before_id is not None
            else None
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="document cursor is invalid",
        ) from None

    try:
        page = await use_case.execute(
            actor_user_id=current_user.id,
            client_folder_id=client_id,
            limit=limit,
            before=cursor,
        )
    except ClientFolderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_CLIENT_NOT_FOUND_DETAIL
        ) from None

    return DocumentListResponse(
        items=[_to_response(document) for document in page.items],
        limit=limit,
        next_cursor=(
            DocumentCursorResponse(
                stored_at=page.next_cursor.stored_at, id=page.next_cursor.id
            )
            if page.next_cursor is not None
            else None
        ),
    )


@router.get("/{client_id}/documents/{document_id}", response_model=DocumentResponse)
async def get_client_document(
    client_id: UUID,
    document_id: UUID,
    current_user: CurrentUser,
    use_case: Annotated[
        GetClientDocumentUseCase, Depends(get_get_client_document_use_case)
    ],
) -> DocumentResponse:
    try:
        document = await use_case.execute(
            actor_user_id=current_user.id,
            client_folder_id=client_id,
            document_id=document_id,
        )
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_DOCUMENT_NOT_FOUND_DETAIL
        ) from None
    return _to_response(document)


@router.get(
    "/{client_id}/documents/{document_id}/content",
    response_class=StreamingResponse,
)
async def export_client_document(
    client_id: UUID,
    document_id: UUID,
    current_user: CurrentUser,
    use_case: Annotated[
        ExportClientDocumentUseCase, Depends(get_export_client_document_use_case)
    ],
) -> StreamingResponse:
    """Entrega uma cópia autorizada; o arquivo original permanece na área privada."""
    try:
        export = await use_case.execute(
            actor_user_id=current_user.id,
            client_folder_id=client_id,
            document_id=document_id,
        )
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_DOCUMENT_NOT_FOUND_DETAIL
        ) from None
    except DocumentContentUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="o arquivo do documento não pôde ser lido no armazenamento local",
        ) from None

    return StreamingResponse(
        export.chunks,
        media_type=export.document.media_type.value,
        headers={
            "Content-Disposition": _content_disposition(
                export.document.original_filename
            ),
            "Content-Length": str(export.document.byte_size),
            "X-Content-Type-Options": "nosniff",
        },
    )
