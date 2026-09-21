"""Rotas autenticadas para modelos e candidatos, ainda sem envio."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from crm_api.application.communications.email_delivery import (
    ConfigureEmailSenderUseCase,
    ConfirmedDeliveryAlreadyExistsError,
    EmailSenderNotConfiguredError,
    GetEmailSenderSettingsUseCase,
    ListEmailDispatchesUseCase,
    RepeatConfirmationRequiredError,
    SendEmailBatchUseCase,
)
from crm_api.application.communications.list_recipient_candidates import (
    ListRecipientCandidatesUseCase,
)
from crm_api.application.communications.render_template import (
    RenderMessageTemplateUseCase,
)
from crm_api.application.communications.templates import (
    CreateMessageTemplateUseCase,
    DeleteMessageTemplateUseCase,
    GetMessageTemplateUseCase,
    ListMessageTemplatesUseCase,
    UpdateMessageTemplateUseCase,
)
from crm_api.domain.communications.entities import (
    EmailDispatch,
    EmailDispatchCursor,
    EmailSenderSettings,
    MessageTemplate,
    RecipientCandidateCursor,
)
from crm_api.domain.communications.errors import MessageTemplateNotFoundError
from crm_api.domain.clients.errors import ClientFolderNotFoundError
from crm_api.domain.documents.entities import DocumentStatus
from crm_api.presentation.auth.dependencies import CurrentUser
from crm_api.presentation.communications.dependencies import (
    get_create_message_template_use_case,
    get_configure_email_sender_use_case,
    get_delete_message_template_use_case,
    get_get_message_template_use_case,
    get_email_sender_settings_use_case,
    get_list_email_dispatches_use_case,
    get_list_message_templates_use_case,
    get_list_recipient_candidates_use_case,
    get_render_message_template_use_case,
    get_send_email_batch_use_case,
    get_update_message_template_use_case,
)
from crm_api.presentation.communications.schemas import (
    EmailDispatchCursorResponse,
    EmailDispatchListResponse,
    EmailDispatchResponse,
    EmailSenderSettingsPayload,
    EmailSenderSettingsResponse,
    MessageTemplatePayload,
    MessageTemplatePreviewRequest,
    MessageTemplatePreviewResponse,
    MessageTemplateResponse,
    RecipientCandidateCursorResponse,
    RecipientCandidateListResponse,
    RecipientCandidateResponse,
    SendEmailBatchRequest,
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


def _settings_response(settings: EmailSenderSettings) -> EmailSenderSettingsResponse:
    return EmailSenderSettingsResponse(
        sender_name=settings.sender_name,
        sender_email=settings.sender_email,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        security=settings.security,
        username=settings.username,
        max_recipients=settings.max_recipients,
    )


def _dispatch_response(dispatch: EmailDispatch) -> EmailDispatchResponse:
    return EmailDispatchResponse(
        id=dispatch.id,
        template_id=dispatch.template_id,
        client_id=dispatch.client_id,
        recipient_email=dispatch.recipient_email,
        subject=dispatch.subject,
        body=dispatch.body,
        message_id=dispatch.message_id,
        retry_of_id=dispatch.retry_of_id,
        retry_of_message_id=dispatch.retry_of_message_id,
        status=dispatch.status,
        detail=dispatch.detail,
        attempted_at=dispatch.attempted_at,
    )


@router.get(
    "/email-sender-settings",
    response_model=EmailSenderSettingsResponse,
)
async def get_email_sender_settings(
    current_user: CurrentUser,
    use_case: Annotated[
        GetEmailSenderSettingsUseCase,
        Depends(get_email_sender_settings_use_case),
    ],
) -> EmailSenderSettingsResponse:
    try:
        return _settings_response(await use_case.execute(actor_user_id=current_user.id))
    except EmailSenderNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="email sender is not configured",
        ) from None


@router.put(
    "/email-sender-settings",
    response_model=EmailSenderSettingsResponse,
)
async def configure_email_sender(
    payload: EmailSenderSettingsPayload,
    current_user: CurrentUser,
    use_case: Annotated[
        ConfigureEmailSenderUseCase,
        Depends(get_configure_email_sender_use_case),
    ],
) -> EmailSenderSettingsResponse:
    try:
        settings = await use_case.execute(
            actor_user_id=current_user.id,
            sender_name=payload.sender_name,
            sender_email=str(payload.sender_email),
            smtp_host=payload.smtp_host,
            smtp_port=payload.smtp_port,
            security=payload.security,
            username=payload.username,
            max_recipients=payload.max_recipients,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _settings_response(settings)


@router.post(
    "/email-dispatches",
    response_model=list[EmailDispatchResponse],
)
async def send_email_batch(
    payload: SendEmailBatchRequest,
    current_user: CurrentUser,
    use_case: Annotated[
        SendEmailBatchUseCase,
        Depends(get_send_email_batch_use_case),
    ],
) -> list[EmailDispatchResponse]:
    try:
        dispatches = await use_case.execute(
            actor_user_id=current_user.id,
            template_id=payload.template_id,
            client_ids=payload.client_ids,
            credential=(
                payload.credential.get_secret_value()
                if payload.credential is not None
                else None
            ),
            confirm_repeat=payload.confirm_repeat,
        )
    except EmailSenderNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email sender is not configured",
        ) from None
    except MessageTemplateNotFoundError:
        raise HTTPException(
            status_code=404, detail="message template not found"
        ) from None
    except RepeatConfirmationRequiredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="repeat confirmation required",
        ) from None
    except ConfirmedDeliveryAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="confirmed delivery cannot be repeated",
        ) from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return [_dispatch_response(item) for item in dispatches]


@router.get(
    "/email-dispatches",
    response_model=EmailDispatchListResponse,
)
async def list_email_dispatches(
    current_user: CurrentUser,
    use_case: Annotated[
        ListEmailDispatchesUseCase,
        Depends(get_list_email_dispatches_use_case),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before_attempted_at: Annotated[datetime | None, Query()] = None,
    before_id: Annotated[UUID | None, Query()] = None,
) -> EmailDispatchListResponse:
    if (before_attempted_at is None) != (before_id is None):
        raise HTTPException(
            status_code=422,
            detail="before_attempted_at and before_id must be provided together",
        )
    cursor = (
        EmailDispatchCursor(attempted_at=before_attempted_at, id=before_id)
        if before_attempted_at is not None and before_id is not None
        else None
    )
    page = await use_case.execute(
        actor_user_id=current_user.id, limit=limit, before=cursor
    )
    return EmailDispatchListResponse(
        items=[_dispatch_response(item) for item in page.items],
        limit=limit,
        next_cursor=(
            EmailDispatchCursorResponse(
                attempted_at=page.next_cursor.attempted_at,
                id=page.next_cursor.id,
            )
            if page.next_cursor is not None
            else None
        ),
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


@router.post(
    "/message-templates/{template_id}/preview",
    response_model=MessageTemplatePreviewResponse,
)
async def preview_message_template(
    template_id: UUID,
    payload: MessageTemplatePreviewRequest,
    current_user: CurrentUser,
    use_case: Annotated[
        RenderMessageTemplateUseCase,
        Depends(get_render_message_template_use_case),
    ],
) -> MessageTemplatePreviewResponse:
    try:
        preview = await use_case.execute(
            actor_user_id=current_user.id,
            template_id=template_id,
            client_id=payload.client_id,
        )
    except MessageTemplateNotFoundError:
        raise HTTPException(
            status_code=404, detail="message template not found"
        ) from None
    except ClientFolderNotFoundError:
        raise HTTPException(status_code=404, detail="client folder not found") from None
    return MessageTemplatePreviewResponse(
        client_id=preview.client_id,
        subject=preview.subject,
        body=preview.body,
    )


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


@router.get("/message-templates/{template_id}", response_model=MessageTemplateResponse)
async def get_message_template(
    template_id: UUID,
    current_user: CurrentUser,
    use_case: Annotated[
        GetMessageTemplateUseCase,
        Depends(get_get_message_template_use_case),
    ],
) -> MessageTemplateResponse:
    del current_user
    try:
        template = await use_case.execute(template_id=template_id)
    except MessageTemplateNotFoundError:
        raise HTTPException(
            status_code=404, detail="message template not found"
        ) from None
    return _to_response(template)


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
    response_model=RecipientCandidateListResponse,
)
async def list_recipient_candidates(
    current_user: CurrentUser,
    use_case: Annotated[
        ListRecipientCandidatesUseCase,
        Depends(get_list_recipient_candidates_use_case),
    ],
    document_status: Annotated[DocumentStatus, Query(alias="status")],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    before_display_name: Annotated[str | None, Query()] = None,
    before_client_id: Annotated[UUID | None, Query()] = None,
) -> RecipientCandidateListResponse:
    if (before_display_name is None) != (before_client_id is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "before_display_name and before_client_id must be provided together"
            ),
        )
    try:
        cursor = (
            RecipientCandidateCursor(
                display_name=before_display_name,
                client_id=before_client_id,
            )
            if before_display_name is not None and before_client_id is not None
            else None
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="recipient candidate cursor is invalid",
        ) from None

    try:
        page = await use_case.execute(
            actor_user_id=current_user.id,
            document_status=document_status,
            limit=limit,
            before=cursor,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return RecipientCandidateListResponse(
        items=[
            RecipientCandidateResponse(
                client_id=item.client_id,
                display_name=item.display_name,
                document_status=item.document_status,
                matching_documents=item.matching_documents,
            )
            for item in page.items
        ],
        limit=limit,
        next_cursor=(
            RecipientCandidateCursorResponse(
                display_name=page.next_cursor.display_name,
                client_id=page.next_cursor.client_id,
            )
            if page.next_cursor is not None
            else None
        ),
    )
