"""Adaptador SQLAlchemy da porta de pasta flexível de clientes."""

from dataclasses import dataclass
from typing import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from crm_api.domain.clients.entities import ClientFolder
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
