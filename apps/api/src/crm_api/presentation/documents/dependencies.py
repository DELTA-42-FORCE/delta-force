"""Fiação HTTP dos casos de uso e adaptadores de documentos."""

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
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
from crm_api.core.config import get_settings
from crm_api.infrastructure.audit.repositories import (
    SqlAlchemyAuditEventRepository,
)
from crm_api.infrastructure.audit.transactions import SqlAlchemyTransaction
from crm_api.infrastructure.clients.repositories import (
    SqlAlchemyClientFolderRepository,
)
from crm_api.infrastructure.documents.repositories import (
    SqlAlchemyDocumentMetadataRepository,
)
from crm_api.infrastructure.documents.storage import (
    PrivateFilesystemDocumentStorage,
)
from crm_api.presentation.dependencies import DatabaseSession


def get_document_storage() -> PrivateFilesystemDocumentStorage:
    """Resolve a raiz privada uma vez por requisição, sem expor o caminho."""
    return PrivateFilesystemDocumentStorage(root=get_settings().documents_root_path)


def get_store_document_use_case(session: DatabaseSession) -> StoreDocumentUseCase:
    return StoreDocumentUseCase(
        clients=SqlAlchemyClientFolderRepository(session),
        documents=SqlAlchemyDocumentMetadataRepository(session),
        storage=get_document_storage(),
        audit=RecordAuditEventUseCase(events=SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )


def get_list_client_documents_use_case(
    session: DatabaseSession,
) -> ListClientDocumentsUseCase:
    return ListClientDocumentsUseCase(
        clients=SqlAlchemyClientFolderRepository(session),
        documents=SqlAlchemyDocumentMetadataRepository(session),
        audit=RecordAuditEventUseCase(events=SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )


def get_get_client_document_use_case(
    session: DatabaseSession,
) -> GetClientDocumentUseCase:
    return GetClientDocumentUseCase(
        documents=SqlAlchemyDocumentMetadataRepository(session),
        audit=RecordAuditEventUseCase(events=SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )


def get_export_client_document_use_case(
    session: DatabaseSession,
) -> ExportClientDocumentUseCase:
    return ExportClientDocumentUseCase(
        documents=SqlAlchemyDocumentMetadataRepository(session),
        storage=get_document_storage(),
        audit=RecordAuditEventUseCase(events=SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )


def get_update_document_status_use_case(
    session: DatabaseSession,
) -> UpdateDocumentStatusUseCase:
    return UpdateDocumentStatusUseCase(
        documents=SqlAlchemyDocumentMetadataRepository(session),
        audit=RecordAuditEventUseCase(events=SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )
