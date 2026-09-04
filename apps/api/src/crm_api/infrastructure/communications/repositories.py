"""Consultas SQLAlchemy de modelos e candidatos a destinatário."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from crm_api.domain.communications.entities import MessageTemplate, RecipientCandidate
from crm_api.domain.documents.entities import DocumentStatus
from crm_api.infrastructure.clients.models import ClientFolderModel
from crm_api.infrastructure.communications.models import MessageTemplateModel
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
        self, *, document_status: DocumentStatus, limit: int
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
            .order_by(ClientFolderModel.display_name.asc(), ClientFolderModel.id.asc())
            .limit(limit)
        )
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
