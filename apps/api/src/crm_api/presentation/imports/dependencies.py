"""Fiação HTTP dos casos de uso da importação do acervo legado (#45)."""

from crm_api.application.imports.preview_legacy_import import (
    PreviewLegacyImportUseCase,
)
from crm_api.infrastructure.clients.repositories import (
    SqlAlchemyClientFolderRepository,
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
