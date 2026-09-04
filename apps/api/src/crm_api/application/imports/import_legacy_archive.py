"""Execução da importação do acervo legado: copia, deduplica e audita (#45).

Cada arquivo elegível (formato válido e um único cliente correspondente) é
copiado por streaming para a área privada, reutilizando o mesmo armazenamento e
os mesmos metadados da gravação normal de documentos. A origem nunca é alterada,
o mesmo conteúdo já anexado ao cliente não entra de novo, e uma falha em um
arquivo é registrada sem interromper os demais.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.transactions import Transaction
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.clients.entities import ClientFolder
from crm_api.domain.clients.repositories import ClientFolderRepository
from crm_api.domain.documents.errors import (
    DocumentStorageError,
    InsufficientStorageError,
    InvalidDocumentNameError,
    UnsupportedDocumentMediaTypeError,
)
from crm_api.domain.documents.entities import StoredContent
from crm_api.domain.documents.naming import normalize_document_filename
from crm_api.domain.documents.repositories import (
    DocumentMetadataRepository,
    DocumentStorage,
)
from crm_api.domain.imports.entities import (
    LegacyImportOutcome,
    LegacyImportResult,
    LegacyImportResultItem,
    LegacyScanEntry,
)
from crm_api.domain.imports.repositories import LegacyArchiveScanner
from crm_api.domain.imports.errors import LegacyImportSourceError


@dataclass(frozen=True, slots=True)
class ImportLegacyArchiveUseCase:
    """Importa os arquivos elegíveis da origem, um a um, de forma auditada."""

    clients: ClientFolderRepository
    documents: DocumentMetadataRepository
    storage: DocumentStorage
    scanner: LegacyArchiveScanner
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self, *, actor_user_id: UUID, source_path: str
    ) -> LegacyImportResult:
        entries = await self.scanner.scan(source_path=source_path)
        matches: dict[str, list[ClientFolder]] = {}
        items: list[LegacyImportResultItem] = []
        for entry in entries:
            items.append(
                await self._import_entry(actor_user_id, source_path, entry, matches)
            )
        return LegacyImportResult(source_path=source_path, items=tuple(items))

    async def _import_entry(
        self,
        actor_user_id: UUID,
        source_path: str,
        entry: LegacyScanEntry,
        matches: dict[str, list[ClientFolder]],
    ) -> LegacyImportResultItem:
        if entry.media_type is None:
            outcome = (
                LegacyImportOutcome.UNSUPPORTED_FORMAT
                if entry.reason == "unsupported_format"
                else LegacyImportOutcome.UNREADABLE
            )
            return self._result(entry, outcome, None)

        if entry.client_folder_name is None:
            return self._result(entry, LegacyImportOutcome.SKIPPED, None)
        candidates = await self._matches_for(entry.client_folder_name, matches)
        if len(candidates) != 1:
            return self._result(entry, LegacyImportOutcome.SKIPPED, None)

        try:
            outcome, document_id = await self._store(
                actor_user_id, source_path, entry, candidates[0]
            )
        except InsufficientStorageError:
            return self._result(entry, LegacyImportOutcome.INSUFFICIENT_SPACE, None)
        except UnsupportedDocumentMediaTypeError:
            # A origem pode ter mudado entre a varredura e a cópia.
            return self._result(entry, LegacyImportOutcome.UNSUPPORTED_FORMAT, None)
        except InvalidDocumentNameError:
            return self._result(entry, LegacyImportOutcome.FAILED, None)
        except LegacyImportSourceError:
            # O arquivo pode ter sido trocado por um link ou removido depois da
            # prévia; isso não deve interromper os demais itens do acervo.
            return self._result(entry, LegacyImportOutcome.UNREADABLE, None)
        except OSError:
            return self._result(entry, LegacyImportOutcome.UNREADABLE, None)
        except DocumentStorageError:
            return self._result(entry, LegacyImportOutcome.FAILED, None)
        except Exception:
            # A execução é resiliente por arquivo. Cancelamentos não entram
            # aqui (`CancelledError` herda BaseException) e continuam a parar a
            # operação com a limpeza feita em `_store`.
            return self._result(entry, LegacyImportOutcome.FAILED, None)
        return self._result(entry, outcome, document_id)

    async def _store(
        self,
        actor_user_id: UUID,
        source_path: str,
        entry: LegacyScanEntry,
        client: ClientFolder,
    ) -> tuple[LegacyImportOutcome, UUID | None]:
        document_id = uuid4()
        filename = normalize_document_filename(PurePosixPath(entry.relative_path).name)
        content: StoredContent | None = None
        try:
            content = await self.storage.store(
                document_id=document_id,
                original_filename=filename,
                chunks=self.scanner.stream_file(
                    source_path=source_path, relative_path=entry.relative_path
                ),
            )
            if await self.documents.checksum_exists(
                client_folder_id=client.id, checksum_sha256=content.checksum_sha256
            ):
                await self.storage.discard(storage_key=content.storage_key)
                return LegacyImportOutcome.DUPLICATE, None

            document = await self.documents.add(
                id=document_id,
                client_folder_id=client.id,
                original_filename=filename,
                content=content,
            )
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.DOCUMENT_STORED,
                resource_type=AuditResourceType.DOCUMENT,
                resource_id=str(document.id),
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except BaseException:
            # Um cancelamento ou falha depois da publicação não pode deixar o
            # arquivo órfão, inclusive durante a checagem de deduplicação.
            await self.transaction.rollback()
            if content is not None:
                await self.storage.discard(storage_key=content.storage_key)
            raise
        return LegacyImportOutcome.IMPORTED, document.id

    async def _matches_for(
        self, folder_name: str, cache: dict[str, list[ClientFolder]]
    ) -> list[ClientFolder]:
        key = folder_name.strip().lower()
        if key not in cache:
            cache[key] = await self.clients.find_by_display_name(
                display_name=folder_name
            )
        return cache[key]

    @staticmethod
    def _result(
        entry: LegacyScanEntry,
        outcome: LegacyImportOutcome,
        document_id: UUID | None,
    ) -> LegacyImportResultItem:
        return LegacyImportResultItem(
            relative_path=entry.relative_path,
            client_folder_name=entry.client_folder_name,
            outcome=outcome,
            document_id=document_id,
        )
