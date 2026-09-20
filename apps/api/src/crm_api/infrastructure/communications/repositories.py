"""Consultas SQLAlchemy de modelos e candidatos a destinatário."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from crm_api.domain.communications.entities import (
    EmailDeliveryStatus,
    EmailDispatch,
    EmailDispatchCursor,
    EmailSenderSettings,
    MessageTemplate,
    RecipientCandidate,
    RecipientCandidateCursor,
    SmtpSecurity,
)
from crm_api.domain.documents.entities import DocumentStatus
from crm_api.infrastructure.clients.models import ClientFolderModel
from crm_api.infrastructure.communications.models import (
    EmailDispatchModel,
    EmailSenderSettingsModel,
    MessageTemplateModel,
)
from crm_api.infrastructure.documents.models import DocumentModel
from crm_api.infrastructure.timestamps import as_utc


def _to_template(model: MessageTemplateModel) -> MessageTemplate:
    return MessageTemplate(
        id=model.id,
        name=model.name,
        subject=model.subject,
        body=model.body,
        created_at=as_utc(model.created_at),
        updated_at=as_utc(model.updated_at),
    )


def _to_sender_settings(model: EmailSenderSettingsModel) -> EmailSenderSettings:
    return EmailSenderSettings(
        sender_name=model.sender_name,
        sender_email=model.sender_email,
        smtp_host=model.smtp_host,
        smtp_port=model.smtp_port,
        security=SmtpSecurity(model.security),
        username=model.username,
        max_recipients=model.max_recipients,
    )


def _to_dispatch(model: EmailDispatchModel) -> EmailDispatch:
    return EmailDispatch(
        id=model.id,
        template_id=model.template_id,
        client_id=model.client_id,
        recipient_email=model.recipient_email,
        subject=model.subject,
        body=model.body,
        message_id=model.message_id,
        status=EmailDeliveryStatus(model.status),
        detail=model.detail,
        attempted_at=as_utc(model.attempted_at),
    )


@dataclass(frozen=True, slots=True)
class SqlAlchemyCommunicationRepository:
    session: AsyncSession

    async def create_template(
        self, *, name: str, subject: str, body: str
    ) -> MessageTemplate:
        model = MessageTemplateModel(name=name, subject=subject, body=body)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return _to_template(model)

    async def list_templates(self) -> list[MessageTemplate]:
        statement = select(MessageTemplateModel).order_by(
            MessageTemplateModel.name.asc(), MessageTemplateModel.id.asc()
        )
        return [
            _to_template(model)
            for model in (await self.session.scalars(statement)).all()
        ]

    async def get_template(self, *, id: UUID) -> MessageTemplate | None:
        model = await self.session.get(MessageTemplateModel, id)
        return _to_template(model) if model is not None else None

    async def update_template(
        self, *, id: UUID, name: str, subject: str, body: str
    ) -> MessageTemplate | None:
        model = await self.session.get(MessageTemplateModel, id)
        if model is None:
            return None
        model.name = name
        model.subject = subject
        model.body = body
        await self.session.flush()
        await self.session.refresh(model)
        return _to_template(model)

    async def delete_template(self, *, id: UUID) -> bool:
        model = await self.session.get(MessageTemplateModel, id)
        if model is None:
            return False
        await self.session.delete(model)
        await self.session.flush()
        return True

    async def list_recipient_candidates(
        self,
        *,
        document_status: DocumentStatus,
        limit: int,
        before: RecipientCandidateCursor | None,
    ) -> list[RecipientCandidate]:
        count = func.count(DocumentModel.id)
        statement = (
            select(
                ClientFolderModel.id,
                ClientFolderModel.display_name,
                count.label("matching_documents"),
            )
            .join(
                DocumentModel,
                DocumentModel.client_folder_id == ClientFolderModel.id,
            )
            .where(DocumentModel.status == document_status.value)
            .group_by(ClientFolderModel.id, ClientFolderModel.display_name)
        )
        if before is not None:
            statement = statement.where(
                or_(
                    ClientFolderModel.display_name > before.display_name,
                    and_(
                        ClientFolderModel.display_name == before.display_name,
                        ClientFolderModel.id > before.client_id,
                    ),
                )
            )
        statement = statement.order_by(
            ClientFolderModel.display_name.asc(), ClientFolderModel.id.asc()
        ).limit(limit)
        rows = (await self.session.execute(statement)).all()
        return [
            RecipientCandidate(
                client_id=row.id,
                display_name=row.display_name,
                document_status=document_status,
                matching_documents=row.matching_documents,
            )
            for row in rows
        ]

    async def get_sender_settings(self) -> EmailSenderSettings | None:
        model = await self.session.get(EmailSenderSettingsModel, 1)
        return _to_sender_settings(model) if model is not None else None

    async def save_sender_settings(
        self, *, settings: EmailSenderSettings
    ) -> EmailSenderSettings:
        model = await self.session.get(EmailSenderSettingsModel, 1)
        if model is None:
            model = EmailSenderSettingsModel(id=1)
            self.session.add(model)
        model.sender_name = settings.sender_name
        model.sender_email = settings.sender_email
        model.smtp_host = settings.smtp_host
        model.smtp_port = settings.smtp_port
        model.security = settings.security.value
        model.username = settings.username
        model.max_recipients = settings.max_recipients
        await self.session.flush()
        await self.session.refresh(model)
        return _to_sender_settings(model)

    async def create_dispatch(
        self,
        *,
        template_id: UUID,
        client_id: UUID,
        recipient_email: str | None,
        subject: str,
        body: str,
        message_id: str,
        status: EmailDeliveryStatus,
        detail: str | None,
    ) -> EmailDispatch:
        model = EmailDispatchModel(
            template_id=template_id,
            client_id=client_id,
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            message_id=message_id,
            status=status.value,
            detail=detail,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return _to_dispatch(model)

    async def update_dispatch_result(
        self,
        *,
        id: UUID,
        status: EmailDeliveryStatus,
        detail: str | None,
    ) -> EmailDispatch:
        model = await self.session.get(EmailDispatchModel, id)
        if model is None:
            raise RuntimeError("email dispatch disappeared during delivery")
        model.status = status.value
        model.detail = detail
        await self.session.flush()
        await self.session.refresh(model)
        return _to_dispatch(model)

    async def has_delivery_requiring_confirmation(
        self, *, template_id: UUID, client_id: UUID
    ) -> bool:
        statement = select(EmailDispatchModel.id).where(
            EmailDispatchModel.template_id == template_id,
            EmailDispatchModel.client_id == client_id,
            EmailDispatchModel.status.in_(
                [
                    EmailDeliveryStatus.SENT.value,
                    EmailDeliveryStatus.UNKNOWN.value,
                ]
            ),
        )
        return (await self.session.scalar(statement)) is not None

    async def list_dispatches(
        self, *, limit: int, before: EmailDispatchCursor | None
    ) -> list[EmailDispatch]:
        statement = select(EmailDispatchModel)
        if before is not None:
            statement = statement.where(
                or_(
                    EmailDispatchModel.attempted_at < before.attempted_at,
                    and_(
                        EmailDispatchModel.attempted_at == before.attempted_at,
                        EmailDispatchModel.id < before.id,
                    ),
                )
            )
        statement = statement.order_by(
            EmailDispatchModel.attempted_at.desc(), EmailDispatchModel.id.desc()
        ).limit(limit)
        return [
            _to_dispatch(model)
            for model in (await self.session.scalars(statement)).all()
        ]
