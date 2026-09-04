"""Adaptador SQLAlchemy da porta de pasta flexível de clientes."""

from dataclasses import dataclass
from typing import Mapping
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from crm_api.domain.clients.entities import ClientFolder, ClientFolderCursor
from crm_api.infrastructure.clients.models import ClientFolderModel
from crm_api.infrastructure.timestamps import as_utc


def _to_client_folder(model: ClientFolderModel) -> ClientFolder:
    return ClientFolder(
        id=model.id,
        display_name=model.display_name,
        profile_data=dict(model.profile_data),
        created_at=as_utc(model.created_at),
        updated_at=as_utc(model.updated_at),
    )


@dataclass(frozen=True, slots=True)
class SqlAlchemyClientFolderRepository:
    """Persiste a pasta de cliente no banco configurado."""

    session: AsyncSession

    async def create(
        self, *, display_name: str, profile_data: Mapping[str, str]
    ) -> ClientFolder:
        model = ClientFolderModel(
            display_name=display_name,
            profile_data=dict(profile_data),
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return _to_client_folder(model)

    async def get(self, *, id: UUID) -> ClientFolder | None:
        model = await self.session.get(ClientFolderModel, id)
        return _to_client_folder(model) if model is not None else None

    async def find_by_display_name(self, *, display_name: str) -> list[ClientFolder]:
        # Casa nome sem diferença de caixa nem de espaços nas bordas, para
        # associar a pasta de origem ao cliente já cadastrado (#45).
        normalized = display_name.strip().lower()
        statement = (
            select(ClientFolderModel)
            .where(func.lower(func.trim(ClientFolderModel.display_name)) == normalized)
            .order_by(ClientFolderModel.display_name.asc(), ClientFolderModel.id.asc())
        )
        models = (await self.session.scalars(statement)).all()
        return [_to_client_folder(model) for model in models]

    async def search(
        self,
        *,
        query: str | None,
        limit: int,
        before: ClientFolderCursor | None,
    ) -> list[ClientFolder]:
        statement = select(ClientFolderModel)
        if query:
            statement = statement.where(
                func.lower(ClientFolderModel.display_name).contains(query.lower())
            )
        if before is not None:
            statement = statement.where(
                or_(
                    ClientFolderModel.display_name > before.display_name,
                    and_(
                        ClientFolderModel.display_name == before.display_name,
                        ClientFolderModel.id > before.id,
                    ),
                )
            )

        statement = statement.order_by(
            ClientFolderModel.display_name.asc(),
            ClientFolderModel.id.asc(),
        ).limit(limit)
        models = (await self.session.scalars(statement)).all()
        return [_to_client_folder(model) for model in models]

    async def update(
        self, *, id: UUID, display_name: str, profile_data: Mapping[str, str]
    ) -> ClientFolder | None:
        model = await self.session.get(ClientFolderModel, id)
        if model is None:
            return None

        model.display_name = display_name
        model.profile_data = dict(profile_data)
        await self.session.flush()
        await self.session.refresh(model)
        return _to_client_folder(model)
