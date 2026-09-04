"""Fiação HTTP dos casos de uso da importação do acervo legado (#45)."""

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.imports.import_legacy_archive import (
    ImportLegacyArchiveUseCase,
)
from crm_api.application.imports.preview_legacy_import import (
    PreviewLegacyImportUseCase,
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
from crm_api.infrastructure.imports.scanner import FilesystemLegacyArchiveScanner
from crm_api.presentation.dependencies import DatabaseSession


def get_preview_legacy_import_use_case(
    session: DatabaseSession,
) -> PreviewLegacyImportUseCase:
    return PreviewLegacyImportUseCase(
        clients=SqlAlchemyClientFolderRepository(session),
        scanner=FilesystemLegacyArchiveScanner(),
    )


def get_import_legacy_archive_use_case(
    session: DatabaseSession,
) -> ImportLegacyArchiveUseCase:
    return ImportLegacyArchiveUseCase(
        clients=SqlAlchemyClientFolderRepository(session),
        documents=SqlAlchemyDocumentMetadataRepository(session),
        storage=PrivateFilesystemDocumentStorage(
            root=get_settings().documents_root_path
        ),
        scanner=FilesystemLegacyArchiveScanner(),
        audit=RecordAuditEventUseCase(events=SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )
