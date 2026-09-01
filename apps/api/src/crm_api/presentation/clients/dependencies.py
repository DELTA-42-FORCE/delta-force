"""Fiação HTTP dos casos de uso e adaptadores da pasta de clientes."""

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.clients.create_client_folder import (
    CreateClientFolderUseCase,
)
from crm_api.application.clients.get_client_folder import GetClientFolderUseCase
from crm_api.application.clients.list_client_folders import (
    ListClientFoldersUseCase,
)
from crm_api.application.clients.update_client_folder import (
    UpdateClientFolderUseCase,
)
from crm_api.infrastructure.audit.repositories import (
    SqlAlchemyAuditEventRepository,
)
from crm_api.infrastructure.audit.transactions import SqlAlchemyTransaction
from crm_api.infrastructure.clients.repositories import (
    SqlAlchemyClientFolderRepository,
)
from crm_api.presentation.dependencies import DatabaseSession


def get_create_client_folder_use_case(
    session: DatabaseSession,
) -> CreateClientFolderUseCase:
    return CreateClientFolderUseCase(
        clients=SqlAlchemyClientFolderRepository(session),
        audit=RecordAuditEventUseCase(events=SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )


def get_get_client_folder_use_case(
    session: DatabaseSession,
) -> GetClientFolderUseCase:
    return GetClientFolderUseCase(
        clients=SqlAlchemyClientFolderRepository(session),
        audit=RecordAuditEventUseCase(events=SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )


def get_list_client_folders_use_case(
    session: DatabaseSession,
) -> ListClientFoldersUseCase:
    return ListClientFoldersUseCase(
        clients=SqlAlchemyClientFolderRepository(session),
        audit=RecordAuditEventUseCase(events=SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )


def get_update_client_folder_use_case(
    session: DatabaseSession,
) -> UpdateClientFolderUseCase:
    return UpdateClientFolderUseCase(
        clients=SqlAlchemyClientFolderRepository(session),
        audit=RecordAuditEventUseCase(events=SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )
