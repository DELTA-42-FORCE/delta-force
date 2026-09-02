"""Árvore privada de documentos, gravada por streaming e publicada de forma atômica.

O diretório é gerenciado pela aplicação, fica fora dos binários e nunca é servido
por URL pública. Nenhum arquivo aparece no destino final antes de o conteúdo ter
sido inteiramente gravado, verificado e sincronizado no disco.
"""

from __future__ import annotations

import asyncio
import errno
import hashlib
import os
import re
import shutil
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from crm_api.domain.documents.entities import DocumentMediaType, StoredContent
from crm_api.domain.documents.errors import (
    DocumentContentUnavailableError,
    DocumentStorageError,
    InsufficientStorageError,
)
from crm_api.domain.documents.naming import (
    assert_extension_matches,
    normalize_document_filename,
)
from crm_api.infrastructure.documents.content import DocumentContentInspector

# Diretório de trabalho da gravação em andamento. Fica dentro da árvore privada
# para que `os.replace` continue atômico, e nada nele é considerado publicado.
INCOMING_DIRECTORY_NAME = "_incoming"

# Margem que preserva o funcionamento do SQLite (WAL, journal e vacuum) mesmo
# quando o disco do proprietário está no limite.
FREE_SPACE_MARGIN_BYTES = 64 * 1024 * 1024
_SPACE_CHECK_INTERVAL_BYTES = 8 * 1024 * 1024
_READ_CHUNK_BYTES = 1024 * 1024
_DIRECTORY_MODE = 0o700
_FILE_MODE = 0o600

_STORAGE_KEY_PATTERN = re.compile(
    r"^[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{32}\.(?:pdf|jpg)$"
)


def provision_document_storage(root: Path) -> Path:
    """Cria a árvore privada de documentos com permissão restrita ao proprietário."""
    root.mkdir(mode=_DIRECTORY_MODE, parents=True, exist_ok=True)
    (root / INCOMING_DIRECTORY_NAME).mkdir(
        mode=_DIRECTORY_MODE, parents=True, exist_ok=True
    )
    return root


@dataclass(frozen=True, slots=True)
class PrivateFilesystemDocumentStorage:
    """Adaptador de filesystem para a porta de armazenamento de documentos."""

    root: Path

    async def store(
        self,
        *,
        document_id: UUID,
        original_filename: str,
        chunks: AsyncIterator[bytes],
    ) -> StoredContent:
        """Grava o fluxo e só publica o arquivo quando ele está íntegro e completo."""
        filename = normalize_document_filename(original_filename)
        temporary_path = self._incoming_path(document_id)
        inspector = DocumentContentInspector()
        digest = hashlib.sha256()
        # A chave é registrada antes de a publicação começar. Se `os.replace`
        # concluir e a etapa seguinte falhar — ou um cancelamento chegar entre
        # elas —, a limpeza ainda alcança o arquivo já publicado. Como a chave
        # deriva de um identificador novo, remover o destino nunca atinge outro
        # documento.
        publishing_key: str | None = None

        try:
            await asyncio.to_thread(provision_document_storage, self.root)
            media_type, byte_size = await self._write_stream(
                temporary_path=temporary_path,
                chunks=chunks,
                inspector=inspector,
                digest=digest,
            )
            assert_extension_matches(filename=filename, media_type=media_type)
            storage_key = self._storage_key(document_id, media_type)
            publishing_key = storage_key
            await asyncio.to_thread(self._publish, temporary_path, storage_key)
        except BaseException:
            # Qualquer falha — formato, disco cheio, cancelamento — não pode
            # deixar conteúdo parcial nem publicado sem metadados na árvore.
            await asyncio.to_thread(self._remove_quietly, temporary_path)
            if publishing_key is not None:
                await asyncio.to_thread(
                    self._remove_quietly, self.resolve_path(publishing_key)
                )
            raise

        return StoredContent(
            storage_key=storage_key,
            media_type=media_type,
            byte_size=byte_size,
            checksum_sha256=digest.hexdigest(),
        )

    async def open_stream(self, *, storage_key: str) -> AsyncIterator[bytes]:
        """Lê um documento publicado em blocos, sem carregá-lo inteiro em memória."""
        path = self.resolve_path(storage_key)
        try:
            handle = await asyncio.to_thread(path.open, "rb")
        except OSError as error:
            raise DocumentContentUnavailableError(
                "the stored document could not be opened"
            ) from error
        try:
            while True:
                chunk = await asyncio.to_thread(handle.read, _READ_CHUNK_BYTES)
                if not chunk:
                    return
                yield chunk
        finally:
            await asyncio.to_thread(handle.close)

    async def discard(self, *, storage_key: str) -> None:
        """Remove um arquivo já publicado, usado quando os metadados não persistem."""
        await asyncio.to_thread(self._remove_quietly, self.resolve_path(storage_key))

    def resolve_path(self, storage_key: str) -> Path:
        """Traduz a chave interna em caminho local; nunca produz URL pública."""
        if not _STORAGE_KEY_PATTERN.fullmatch(storage_key):
            raise DocumentStorageError("document storage key is invalid")
        return self.root.joinpath(*storage_key.split("/"))

    async def _write_stream(
        self,
        *,
        temporary_path: Path,
        chunks: AsyncIterator[bytes],
        inspector: DocumentContentInspector,
        digest: "hashlib._Hash",
    ) -> tuple[DocumentMediaType, int]:
        await asyncio.to_thread(self._require_free_space)
        handle = await asyncio.to_thread(self._open_exclusively, temporary_path)
        try:
            unchecked_bytes = 0
            async for chunk in chunks:
                if not chunk:
                    continue
                # A inspeção vem antes da escrita para que um formato recusado
                # não chegue a ocupar espaço além do bloco corrente.
                inspector.update(chunk)
                digest.update(chunk)
                await asyncio.to_thread(self._write_chunk, handle, chunk)

                unchecked_bytes += len(chunk)
                if unchecked_bytes >= _SPACE_CHECK_INTERVAL_BYTES:
                    unchecked_bytes = 0
                    await asyncio.to_thread(self._require_free_space)
            await asyncio.to_thread(self._flush_to_disk, handle)
        finally:
            await asyncio.to_thread(handle.close)
        return inspector.finish()

    def _incoming_path(self, document_id: UUID) -> Path:
        return self.root / INCOMING_DIRECTORY_NAME / f"{document_id.hex}.partial"

    @staticmethod
    def _storage_key(document_id: UUID, media_type: DocumentMediaType) -> str:
        identifier = document_id.hex
        return (
            f"{identifier[:2]}/{identifier[2:4]}/"
            f"{identifier}{media_type.canonical_extension}"
        )

    def _require_free_space(self) -> None:
        free_bytes = shutil.disk_usage(self.root).free
        if free_bytes <= FREE_SPACE_MARGIN_BYTES:
            raise InsufficientStorageError(
                "the disk does not have enough free space to store the document"
            )

    @staticmethod
    def _open_exclusively(path: Path) -> BinaryIO:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags, _FILE_MODE)
        return os.fdopen(descriptor, "wb")

    @staticmethod
    def _write_chunk(handle: BinaryIO, chunk: bytes) -> None:
        try:
            handle.write(chunk)
        except OSError as error:
            if error.errno == errno.ENOSPC:
                raise InsufficientStorageError(
                    "the disk ran out of space while storing the document"
                ) from error
            raise

    @staticmethod
    def _flush_to_disk(handle: BinaryIO) -> None:
        try:
            handle.flush()
            os.fsync(handle.fileno())
        except OSError as error:
            if error.errno == errno.ENOSPC:
                raise InsufficientStorageError(
                    "the disk ran out of space while storing the document"
                ) from error
            raise

    def _publish(self, temporary_path: Path, storage_key: str) -> None:
        destination = self.resolve_path(storage_key)
        destination.parent.mkdir(mode=_DIRECTORY_MODE, parents=True, exist_ok=True)
        os.replace(temporary_path, destination)
        self._sync_directory(destination.parent)

    @staticmethod
    def _sync_directory(directory: Path) -> None:
        # O Windows não permite abrir um diretório para fsync; lá a atomicidade
        # de `os.replace` já é garantida pelo próprio sistema de arquivos.
        if os.name != "posix":
            return
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _remove_quietly(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # A limpeza é o melhor esforço: um resíduo em `_incoming` nunca é
            # visível como documento e não pode mascarar o erro original.
            pass
