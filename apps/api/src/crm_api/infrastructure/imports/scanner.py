"""Varredura da pasta de origem do acervo legado, somente leitura (#45).

A origem segue a convenção confirmada: uma pasta por cliente, cujo nome é o nome
do cliente, com os documentos dentro (podendo haver subpastas). A varredura
nunca escreve, não segue symlinks e classifica cada arquivo pelo conteúdo real,
reutilizando o mesmo reconhecimento da gravação de documentos.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

from crm_api.domain.documents.entities import DocumentMediaType
from crm_api.domain.documents.errors import UnsupportedDocumentMediaTypeError
from crm_api.domain.documents.naming import assert_extension_matches
from crm_api.infrastructure.documents.content import DocumentContentInspector
from crm_api.domain.imports.entities import LegacyScanEntry
from crm_api.domain.imports.errors import LegacyImportSourceError

# Teto defensivo: uma origem com dezenas de milhares de arquivos indica pasta
# errada, não o acervo (~500) descrito na #45.
_MAX_FILES = 20_000
_READ_CHUNK_BYTES = 1024 * 1024
_ACCEPTED_SUFFIXES = frozenset({".pdf", ".jpg", ".jpeg"})


@dataclass(frozen=True, slots=True)
class FilesystemLegacyArchiveScanner:
    """Lê a árvore de origem local e devolve os arquivos já classificados."""

    async def scan(self, *, source_path: str) -> list[LegacyScanEntry]:
        return await asyncio.to_thread(self._scan, source_path)

    def _scan(self, source_path: str) -> list[LegacyScanEntry]:
        root = Path(source_path)
        if not root.is_dir():
            raise LegacyImportSourceError(
                "the source path does not exist or is not a directory"
            )

        entries: list[LegacyScanEntry] = []
        for directory, _subdirs, filenames in os.walk(root, followlinks=False):
            for filename in filenames:
                absolute = Path(directory) / filename
                relative = absolute.relative_to(root)
                entries.append(self._classify(absolute, relative, filename))
                if len(entries) > _MAX_FILES:
                    raise LegacyImportSourceError(
                        "the source folder has more files than the importer supports"
                    )
        entries.sort(key=lambda entry: entry.relative_path)
        return entries

    def _classify(
        self, absolute: Path, relative: Path, filename: str
    ) -> LegacyScanEntry:
        parts = relative.parts
        # O primeiro nível sob a raiz é a pasta do cliente; um arquivo solto na
        # raiz não pertence a nenhuma pasta e não pode ser associado.
        client_folder_name = parts[0] if len(parts) > 1 else None
        relative_path = relative.as_posix()

        if Path(filename).suffix.lower() not in _ACCEPTED_SUFFIXES:
            return LegacyScanEntry(
                client_folder_name=client_folder_name,
                relative_path=relative_path,
                media_type=None,
                reason="unsupported_format",
            )

        media_type, reason = self._inspect(absolute, filename)
        return LegacyScanEntry(
            client_folder_name=client_folder_name,
            relative_path=relative_path,
            media_type=media_type,
            reason=reason,
        )

    @staticmethod
    def _inspect(
        absolute: Path, filename: str
    ) -> tuple[DocumentMediaType | None, str | None]:
        inspector = DocumentContentInspector()
        try:
            with absolute.open("rb") as handle:
                while True:
                    chunk = handle.read(_READ_CHUNK_BYTES)
                    if not chunk:
                        break
                    inspector.update(chunk)
            media_type, _size = inspector.finish()
            assert_extension_matches(filename=filename, media_type=media_type)
        except UnsupportedDocumentMediaTypeError:
            # Formato não suportado, extensão que contradiz o conteúdo, ou PDF/JPEG
            # truncado: tudo entra como formato inválido para a revisão.
            return None, "unsupported_format"
        except OSError:
            return None, "unreadable"
        return media_type, None
