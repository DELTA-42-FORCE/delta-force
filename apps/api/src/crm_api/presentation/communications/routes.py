"""Rotas autenticadas para modelos e candidatos, ainda sem envio."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from crm_api.application.communications.list_recipient_candidates import (
    ListRecipientCandidatesUseCase,
)
from crm_api.application.communications.templates import (
    CreateMessageTemplateUseCase,
    DeleteMessageTemplateUseCase,
    ListMessageTemplatesUseCase,
    UpdateMessageTemplateUseCase,
)
from crm_api.domain.communications.entities import MessageTemplate
from crm_api.domain.communications.errors import MessageTemplateNotFoundError
from crm_api.domain.documents.entities import DocumentStatus
from crm_api.presentation.auth.dependencies import CurrentUser
from crm_api.presentation.communications.dependencies import (
    get_create_message_template_use_case,
    get_delete_message_template_use_case,
    get_list_message_templates_use_case,
    get_list_recipient_candidates_use_case,
    get_update_message_template_use_case,
)
from crm_api.presentation.communications.schemas import (
    MessageTemplatePayload,
    MessageTemplateResponse,
    RecipientCandidateResponse,
)

router = APIRouter(tags=["communications"])


def _to_response(template: MessageTemplate) -> MessageTemplateResponse:
    return MessageTemplateResponse(
        id=template.id,
        name=template.name,
        subject=template.subject,
        body=template.body,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.post(
    "/message-templates",
    response_model=MessageTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_message_template(
    payload: MessageTemplatePayload,
    current_user: CurrentUser,
    use_case: Annotated[
        CreateMessageTemplateUseCase,
        Depends(get_create_message_template_use_case),
    ],
) -> MessageTemplateResponse:
    try:
        template = await use_case.execute(
            actor_user_id=current_user.id,
            name=payload.name,
            subject=payload.subject,
            body=payload.body,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _to_response(template)


@router.get("/message-templates", response_model=list[MessageTemplateResponse])
async def list_message_templates(
    current_user: CurrentUser,
    use_case: Annotated[
        ListMessageTemplatesUseCase,
        Depends(get_list_message_templates_use_case),
    ],
) -> list[MessageTemplateResponse]:
    del current_user
    return [_to_response(item) for item in await use_case.execute()]


@router.put("/message-templates/{template_id}", response_model=MessageTemplateResponse)
async def update_message_template(
    template_id: UUID,
    payload: MessageTemplatePayload,
    current_user: CurrentUser,
    use_case: Annotated[
        UpdateMessageTemplateUseCase,
        Depends(get_update_message_template_use_case),
    ],
) -> MessageTemplateResponse:
    try:
        template = await use_case.execute(
            actor_user_id=current_user.id,
            template_id=template_id,
            name=payload.name,
            subject=payload.subject,
            body=payload.body,
        )
    except MessageTemplateNotFoundError:
        raise HTTPException(
            status_code=404, detail="message template not found"
        ) from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _to_response(template)


@router.delete(
    "/message-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_message_template(
    template_id: UUID,
    current_user: CurrentUser,
    use_case: Annotated[
        DeleteMessageTemplateUseCase,
        Depends(get_delete_message_template_use_case),
    ],
) -> Response:
    try:
        await use_case.execute(actor_user_id=current_user.id, template_id=template_id)
    except MessageTemplateNotFoundError:
        raise HTTPException(
            status_code=404, detail="message template not found"
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/email-recipient-candidates",
    response_model=list[RecipientCandidateResponse],
)
async def list_recipient_candidates(
    current_user: CurrentUser,
    use_case: Annotated[
        ListRecipientCandidatesUseCase,
        Depends(get_list_recipient_candidates_use_case),
    ],
    document_status: Annotated[DocumentStatus, Query(alias="status")],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[RecipientCandidateResponse]:
    del current_user
    try:
        candidates = await use_case.execute(
            document_status=document_status, limit=limit
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return [
        RecipientCandidateResponse(
            client_id=item.client_id,
            display_name=item.display_name,
            document_status=item.document_status,
            matching_documents=item.matching_documents,
        )
        for item in candidates
    ]
