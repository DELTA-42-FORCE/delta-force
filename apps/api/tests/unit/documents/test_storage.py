import asyncio
import errno
import hashlib
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

import pytest

from crm_api.domain.documents.entities import DocumentMediaType
from crm_api.domain.documents.errors import (
    DocumentContentUnavailableError,
    DocumentStorageError,
    InsufficientStorageError,
    InvalidDocumentNameError,
    UnsupportedDocumentMediaTypeError,
)
from crm_api.infrastructure.documents import storage as storage_module
from crm_api.infrastructure.documents.storage import (
    INCOMING_DIRECTORY_NAME,
    PrivateFilesystemDocumentStorage,
    provision_document_storage,
)

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x11" * 64 + b"\xff\xd9"

DOCUMENT_ID = UUID("0123456789abcdef0123456789abcdef")


async def _stream(payload: bytes, *, chunk_size: int = 16) -> AsyncIterator[bytes]:
    for start in range(0, len(payload), chunk_size):
        end = start + chunk_size
        yield payload[start:end]


def _published_files(root: Path) -> list[Path]:
    incoming = root / INCOMING_DIRECTORY_NAME
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and incoming not in path.parents
    )


def _incoming_files(root: Path) -> list[Path]:
    return sorted(path for path in (root / INCOMING_DIRECTORY_NAME).glob("*"))


@pytest.fixture
def document_storage(tmp_path: Path) -> PrivateFilesystemDocumentStorage:
    return PrivateFilesystemDocumentStorage(root=tmp_path / "documents")


async def test_stores_a_pdf_under_a_key_derived_only_from_the_identifier(
    document_storage: PrivateFilesystemDocumentStorage,
) -> None:
    content = await document_storage.store(
        document_id=DOCUMENT_ID,
        original_filename="contrato assinado.pdf",
        chunks=_stream(PDF_BYTES),
    )

    assert content.storage_key == ("01/23/0123456789abcdef0123456789abcdef.pdf")
    assert content.media_type is DocumentMediaType.PDF
    assert content.byte_size == len(PDF_BYTES)
    assert content.checksum_sha256 == hashlib.sha256(PDF_BYTES).hexdigest()

    stored_path = document_storage.resolve_path(content.storage_key)
    assert stored_path.read_bytes() == PDF_BYTES
    assert _incoming_files(document_storage.root) == []


async def test_stores_a_jpeg_declared_with_either_accepted_extension(
    document_storage: PrivateFilesystemDocumentStorage,
) -> None:
    content = await document_storage.store(
        document_id=uuid4(),
        original_filename="digitalizacao.jpeg",
        chunks=_stream(JPEG_BYTES),
    )

    assert content.media_type is DocumentMediaType.JPEG
    assert content.storage_key.endswith(".jpg")
    assert document_storage.resolve_path(content.storage_key).read_bytes() == JPEG_BYTES


async def test_rejects_content_that_is_not_a_supported_document(
    document_storage: PrivateFilesystemDocumentStorage,
) -> None:
    with pytest.raises(UnsupportedDocumentMediaTypeError):
        await document_storage.store(
            document_id=DOCUMENT_ID,
            original_filename="planilha.pdf",
            chunks=_stream(b"PK\x03\x04conteudo compactado"),
        )

    assert _published_files(document_storage.root) == []
    assert _incoming_files(document_storage.root) == []


async def test_rejects_a_jpeg_renamed_as_pdf_without_publishing_it(
    document_storage: PrivateFilesystemDocumentStorage,
) -> None:
    with pytest.raises(UnsupportedDocumentMediaTypeError, match="does not match"):
        await document_storage.store(
            document_id=DOCUMENT_ID,
            original_filename="disfarcado.pdf",
            chunks=_stream(JPEG_BYTES),
        )

    assert _published_files(document_storage.root) == []
    assert _incoming_files(document_storage.root) == []


async def test_rejects_an_unsafe_name_before_touching_the_disk(
    document_storage: PrivateFilesystemDocumentStorage,
) -> None:
    with pytest.raises(InvalidDocumentNameError):
        await document_storage.store(
            document_id=DOCUMENT_ID,
            original_filename="../escapando.pdf",
            chunks=_stream(PDF_BYTES),
        )

    assert not document_storage.root.exists()


async def test_rejects_a_truncated_document_without_publishing_it(
    document_storage: PrivateFilesystemDocumentStorage,
) -> None:
    with pytest.raises(UnsupportedDocumentMediaTypeError, match="truncated"):
        await document_storage.store(
            document_id=DOCUMENT_ID,
            original_filename="incompleto.pdf",
            chunks=_stream(PDF_BYTES.replace(b"%%EOF\n", b"")),
        )

    assert _published_files(document_storage.root) == []
    assert _incoming_files(document_storage.root) == []


async def test_refuses_to_start_when_the_disk_is_already_near_capacity(
    document_storage: PrivateFilesystemDocumentStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        storage_module.shutil,
        "disk_usage",
        lambda path: _usage(free=storage_module.FREE_SPACE_MARGIN_BYTES),
    )

    with pytest.raises(InsufficientStorageError, match="enough free space"):
        await document_storage.store(
            document_id=DOCUMENT_ID,
            original_filename="contrato.pdf",
            chunks=_stream(PDF_BYTES),
        )

    assert _published_files(document_storage.root) == []
    assert _incoming_files(document_storage.root) == []


async def test_aborts_and_cleans_up_when_free_space_drops_during_the_write(
    document_storage: PrivateFilesystemDocumentStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    readings = iter(
        [
            _usage(free=storage_module.FREE_SPACE_MARGIN_BYTES * 4),
            _usage(free=storage_module.FREE_SPACE_MARGIN_BYTES // 2),
        ]
    )
    monkeypatch.setattr(storage_module, "_SPACE_CHECK_INTERVAL_BYTES", 16)
    monkeypatch.setattr(
        storage_module.shutil,
        "disk_usage",
        lambda path: next(readings, _usage(free=0)),
    )

    with pytest.raises(InsufficientStorageError):
        await document_storage.store(
            document_id=DOCUMENT_ID,
            original_filename="contrato.pdf",
            chunks=_stream(PDF_BYTES, chunk_size=16),
        )

    assert _published_files(document_storage.root) == []
    assert _incoming_files(document_storage.root) == []


async def test_translates_a_full_disk_error_and_removes_the_partial_file(
    document_storage: PrivateFilesystemDocumentStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    open_exclusively = PrivateFilesystemDocumentStorage._open_exclusively
    monkeypatch.setattr(
        PrivateFilesystemDocumentStorage,
        "_open_exclusively",
        staticmethod(lambda path: _FullDiskHandle(open_exclusively(path))),
    )

    with pytest.raises(InsufficientStorageError, match="ran out of space"):
        await document_storage.store(
            document_id=DOCUMENT_ID,
            original_filename="contrato.pdf",
            chunks=_stream(PDF_BYTES, chunk_size=16),
        )

    assert _published_files(document_storage.root) == []
    assert _incoming_files(document_storage.root) == []


async def test_removes_the_published_file_when_publishing_fails_after_the_replace(
    document_storage: PrivateFilesystemDocumentStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regressão: falha depois do `os.replace` não pode deixar arquivo órfão.

    O arquivo já está no destino final, mas sem metadados nem auditoria ele
    seria invisível para o CRM e para o backup da #44.
    """

    def explode_after_replace(directory: Path) -> None:
        raise OSError("directory sync failed")

    monkeypatch.setattr(
        PrivateFilesystemDocumentStorage,
        "_sync_directory",
        staticmethod(explode_after_replace),
    )

    with pytest.raises(OSError, match="directory sync failed"):
        await document_storage.store(
            document_id=DOCUMENT_ID,
            original_filename="contrato.pdf",
            chunks=_stream(PDF_BYTES),
        )

    assert _published_files(document_storage.root) == []
    assert _incoming_files(document_storage.root) == []


async def test_removes_the_partial_file_when_the_upload_is_cancelled(
    document_storage: PrivateFilesystemDocumentStorage,
) -> None:
    async def interrupted() -> AsyncIterator[bytes]:
        yield PDF_BYTES[:16]
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await document_storage.store(
            document_id=DOCUMENT_ID,
            original_filename="contrato.pdf",
            chunks=interrupted(),
        )

    assert _published_files(document_storage.root) == []
    assert _incoming_files(document_storage.root) == []


async def test_discard_removes_a_published_document(
    document_storage: PrivateFilesystemDocumentStorage,
) -> None:
    content = await document_storage.store(
        document_id=DOCUMENT_ID,
        original_filename="contrato.pdf",
        chunks=_stream(PDF_BYTES),
    )

    await document_storage.discard(storage_key=content.storage_key)

    assert not document_storage.resolve_path(content.storage_key).exists()
    # A remoção repetida é tolerada porque o rollback pode competir com o retry.
    await document_storage.discard(storage_key=content.storage_key)


async def test_open_stream_reads_back_exactly_what_was_stored(
    document_storage: PrivateFilesystemDocumentStorage,
) -> None:
    content = await document_storage.store(
        document_id=DOCUMENT_ID,
        original_filename="contrato.pdf",
        chunks=_stream(PDF_BYTES),
    )

    read_back = b"".join(
        [
            chunk
            async for chunk in document_storage.open_stream(
                storage_key=content.storage_key
            )
        ]
    )

    assert read_back == PDF_BYTES


async def test_open_stream_reports_a_missing_file_instead_of_yielding_nothing(
    document_storage: PrivateFilesystemDocumentStorage,
) -> None:
    content = await document_storage.store(
        document_id=DOCUMENT_ID,
        original_filename="contrato.pdf",
        chunks=_stream(PDF_BYTES),
    )
    document_storage.resolve_path(content.storage_key).unlink()

    with pytest.raises(DocumentContentUnavailableError):
        async for _ in document_storage.open_stream(storage_key=content.storage_key):
            pass


async def test_open_stream_translates_a_read_failure_after_the_first_block(
    document_storage: PrivateFilesystemDocumentStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uma leitura que falha no meio do arquivo vira erro de domínio, não OSError."""
    content = await document_storage.store(
        document_id=DOCUMENT_ID,
        original_filename="contrato.pdf",
        chunks=_stream(PDF_BYTES),
    )

    real_open = Path.open

    def open_failing_after_first_read(self: Path, *args: object, **kwargs: object):
        handle = real_open(self, *args, **kwargs)
        return _ReadOnceThenFailHandle(handle)

    monkeypatch.setattr(Path, "open", open_failing_after_first_read)

    read_chunks = 0
    with pytest.raises(DocumentContentUnavailableError):
        async for _ in document_storage.open_stream(storage_key=content.storage_key):
            read_chunks += 1

    assert read_chunks == 1  # o primeiro bloco saiu antes da falha


@pytest.mark.parametrize(
    "storage_key",
    [
        "../../etc/passwd",
        "01/23/0123456789abcdef0123456789abcdef.exe",
        "01/0123456789abcdef0123456789abcdef.pdf",
        "01/23/../../escape.pdf",
        "",
    ],
)
async def test_resolve_path_rejects_a_key_it_did_not_generate(
    document_storage: PrivateFilesystemDocumentStorage, storage_key: str
) -> None:
    with pytest.raises(DocumentStorageError, match="storage key is invalid"):
        document_storage.resolve_path(storage_key)


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_provisioning_restricts_the_private_tree_to_the_owner(tmp_path: Path) -> None:
    root = provision_document_storage(tmp_path / "documents")

    assert root.stat().st_mode & 0o777 == 0o700
    assert (root / INCOMING_DIRECTORY_NAME).stat().st_mode & 0o777 == 0o700


def test_provisioning_is_idempotent(tmp_path: Path) -> None:
    root = provision_document_storage(tmp_path / "documents")

    assert provision_document_storage(root) == root
    assert (root / INCOMING_DIRECTORY_NAME).is_dir()


class _Usage:
    """Substitui `shutil.disk_usage` sem depender do disco real do runner."""

    __slots__ = ("total", "used", "free")

    def __init__(self, *, free: int) -> None:
        self.total = free * 2 or 1
        self.used = self.total - free
        self.free = free


def _usage(*, free: int) -> _Usage:
    return _Usage(free=free)


class _ReadOnceThenFailHandle:
    """Entrega o primeiro bloco e depois falha, como um setor ilegível no meio."""

    def __init__(self, wrapped: BinaryIO) -> None:
        self._wrapped = wrapped
        self._reads = 0

    def read(self, size: int = -1) -> bytes:
        self._reads += 1
        if self._reads == 1:
            return self._wrapped.read(size)
        raise OSError(errno.EIO, "Input/output error")

    def close(self) -> None:
        self._wrapped.close()


class _FullDiskHandle:
    """Escreve normalmente até o disco 'encher' no meio do fluxo."""

    def __init__(self, wrapped: BinaryIO) -> None:
        self._wrapped = wrapped
        self._written = 0

    def write(self, chunk: bytes) -> int:
        if self._written >= 16:
            raise OSError(errno.ENOSPC, "No space left on device")
        self._written += len(chunk)
        return self._wrapped.write(chunk)

    def flush(self) -> None:
        self._wrapped.flush()

    def fileno(self) -> int:
        return self._wrapped.fileno()

    def close(self) -> None:
        self._wrapped.close()
