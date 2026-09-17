"""Rotas HTTP autenticadas de anexo, consulta e exportação de documentos."""

from collections.abc import AsyncIterator
from datetime import datetime
import re
from typing import Annotated
from urllib.parse import quote, unquote_to_bytes
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
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
from crm_api.application.documents.update_document_status import (
    UpdateDocumentStatusUseCase,
)
from crm_api.domain.clients.errors import ClientFolderNotFoundError
from crm_api.domain.documents.entities import (
    DocumentCursor,
    DocumentStatus,
    StoredDocument,
)
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
    get_update_document_status_use_case,
)
from crm_api.presentation.documents.schemas import (
    DocumentCursorResponse,
    DocumentListResponse,
    DocumentResponse,
    UpdateDocumentStatusRequest,
)

router = APIRouter(prefix="/clients", tags=["documents"])

_CLIENT_NOT_FOUND_DETAIL = "client folder not found"
_DOCUMENT_NOT_FOUND_DETAIL = "document not found"
_UPLOAD_CHUNK_BYTES = 1024 * 1024
_INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")


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
        status=document.status,
    )


async def _upload_chunks(request: Request) -> AsyncIterator[bytes]:
    """Entrega o corpo bruto sem o spool temporário criado pelo multipart."""
    async for received in request.stream():
        for start in range(0, len(received), _UPLOAD_CHUNK_BYTES):
            end = start + _UPLOAD_CHUNK_BYTES
            yield received[start:end]


def _decode_upload_metadata(value: str | None) -> str | None:
    if value is None:
        return None
    if not value.isascii() or _INVALID_PERCENT_ESCAPE.search(value):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="metadado do documento possui codificação inválida",
        )
    try:
        return unquote_to_bytes(value).decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="metadado do documento possui codificação inválida",
        ) from None


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
    request: Request,
    current_user: CurrentUser,
    use_case: Annotated[StoreDocumentUseCase, Depends(get_store_document_use_case)],
    encoded_filename: Annotated[
        str,
        Header(alias="X-Delta-Document-Filename", min_length=1, max_length=3_000),
    ],
    encoded_title: Annotated[
        str | None, Header(alias="X-Delta-Document-Title", max_length=1_500)
    ] = None,
    encoded_category: Annotated[
        str | None, Header(alias="X-Delta-Document-Category", max_length=1_000)
    ] = None,
    encoded_notes: Annotated[
        str | None, Header(alias="X-Delta-Document-Notes", max_length=24_000)
    ] = None,
) -> DocumentResponse:
    filename = _decode_upload_metadata(encoded_filename)
    title = _decode_upload_metadata(encoded_title)
    category = _decode_upload_metadata(encoded_category)
    notes = _decode_upload_metadata(encoded_notes)
    if filename is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="o arquivo enviado precisa ter um nome",
        )
    try:
        document = await use_case.execute(
            actor_user_id=current_user.id,
            client_folder_id=client_id,
            original_filename=filename,
            chunks=_upload_chunks(request),
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
    document_status: Annotated[DocumentStatus | None, Query(alias="status")] = None,
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
            document_status=document_status,
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


@router.patch(
    "/{client_id}/documents/{document_id}/status",
    response_model=DocumentResponse,
)
async def update_document_status(
    client_id: UUID,
    document_id: UUID,
    payload: UpdateDocumentStatusRequest,
    current_user: CurrentUser,
    use_case: Annotated[
        UpdateDocumentStatusUseCase,
        Depends(get_update_document_status_use_case),
    ],
) -> DocumentResponse:
    try:
        document = await use_case.execute(
            actor_user_id=current_user.id,
            client_folder_id=client_id,
            document_id=document_id,
            status=payload.status,
        )
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_DOCUMENT_NOT_FOUND_DETAIL,
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
