"""Publish an already-encrypted backup atomically to validated external media."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import stat
from typing import BinaryIO, Callable

from crm_api.infrastructure.backups import container
from crm_api.infrastructure.backups.windows_volume import (
    UnsafeBackupDestinationError,
    WindowsVolumeInspector,
)

MIN_FREE_SPACE_MARGIN_BYTES = 64 * 1024 * 1024
_READ_CHUNK_BYTES = 1024 * 1024


class BackupPublicationError(RuntimeError):
    """A backup could not be safely published to the selected destination."""


@dataclass(frozen=True, slots=True)
class PublishedBackup:
    filename: str
    size_bytes: int
    sha256: str
    volume_id: str


@dataclass(slots=True)
class _OwnedPartial:
    path: Path
    output: BinaryIO
    identity: tuple[int, int]
    cleanup_handle: object | None = None
    kernel32: object | None = None

    def finish(self, *, committed: bool) -> None:
        if not self.output.closed:
            self.output.close()
        if self.cleanup_handle is not None and self.kernel32 is not None:
            if not committed:
                try:
                    _mark_handle_for_deletion(self.kernel32, self.cleanup_handle)
                except OSError:
                    pass
            try:
                self.kernel32.CloseHandle(self.cleanup_handle)
            except OSError:
                pass
            return
        if not committed:
            _unlink_if_owned(self.path, self.identity)


def estimate_encrypted_size(payload_bytes: int) -> int:
    """Return a conservative physical-size bound for the DFCRMBK1 v1 codec."""
    try:
        return container.maximum_encrypted_size(payload_bytes)
    except container.InvalidBackupFormatError as exc:
        raise BackupPublicationError("backup payload size is invalid") from exc


def publish_backup_file(
    *,
    payload_bytes: int,
    destination_directory: Path,
    expected_data_volume_id: str,
    inspector: WindowsVolumeInspector,
    write_encrypted_partial: Callable[[BinaryIO], object],
) -> PublishedBackup:
    """Encrypt to a unique partial stream, then publish and verify without overwrite."""
    if not expected_data_volume_id:
        raise BackupPublicationError("data volume identity is required")
    required_bytes = (
        estimate_encrypted_size(payload_bytes) + MIN_FREE_SPACE_MARGIN_BYTES
    )
    partial_path: Path | None = None
    final_path: Path | None = None
    owned_identity: tuple[int, int] | None = None
    published_identity: tuple[int, int] | None = None
    owned_partial: _OwnedPartial | None = None
    verified = False
    try:
        with inspector.open_directory(
            destination_directory,
            expected_data_volume_id=expected_data_volume_id,
        ) as volume:
            identity = volume.identity
            canonical_directory = identity.canonical_directory
            if shutil.disk_usage(canonical_directory).free < required_bytes:
                raise BackupPublicationError(
                    "external volume has insufficient free space"
                )

            token = secrets.token_hex(16)
            partial_path = canonical_directory / f".delta-force-{token}.partial"
            final_path = canonical_directory / f"backup-{token}.dfcrmbak"
            owned_partial = _create_owned_partial(partial_path)
            owned_identity = owned_partial.identity
            with owned_partial.output as output:
                write_encrypted_partial(output)
                output.flush()
                os.fsync(output.fileno())

            if (
                _file_identity(partial_path.stat(follow_symlinks=False))
                != owned_identity
            ):
                raise BackupPublicationError("encrypted partial identity changed")
            written_size, digest = _sha256_file(partial_path, owned_partial)
            with _open_owned_for_read(owned_partial, partial_path) as source:
                header = container.read_backup_header_from_stream(source)
            if header.payload_bytes != payload_bytes:
                raise BackupPublicationError("encrypted backup payload size is invalid")
            if written_size > estimate_encrypted_size(payload_bytes):
                raise BackupPublicationError("encrypted backup exceeds its size bound")
            if written_size < payload_bytes:
                raise BackupPublicationError("encrypted backup is incomplete")

            _revalidate_volume(
                inspector,
                destination_directory,
                expected_data_volume_id,
                identity.volume_id,
                identity.canonical_directory,
            )
            partial_stat = partial_path.stat(follow_symlinks=False)
            if (
                not stat.S_ISREG(partial_stat.st_mode)
                or _file_identity(partial_stat) != owned_identity
            ):
                raise BackupPublicationError("encrypted partial is not a regular file")
            published_identity = owned_identity
            _rename_no_replace(partial_path, final_path)

            current_volume = _revalidate_volume(
                inspector,
                destination_directory,
                expected_data_volume_id,
                identity.volume_id,
                identity.canonical_directory,
            )
            final_stat = final_path.stat(follow_symlinks=False)
            if (
                not stat.S_ISREG(final_stat.st_mode)
                or _file_identity(final_stat) != published_identity
            ):
                raise BackupPublicationError(
                    "published backup identity verification failed"
                )
            verified_size, verified_digest = _sha256_file(final_path, owned_partial)
            if verified_size != written_size or verified_digest != digest:
                raise BackupPublicationError(
                    "published backup integrity verification failed"
                )
            verified = True
            return PublishedBackup(
                filename=final_path.name,
                size_bytes=verified_size,
                sha256=verified_digest,
                volume_id=current_volume.identity.volume_id,
            )
    except BackupPublicationError:
        raise
    except (OSError, UnsafeBackupDestinationError, ValueError):
        raise BackupPublicationError("backup could not be published safely") from None
    finally:
        if owned_partial is not None:
            owned_partial.finish(committed=verified)
        if not verified and final_path is not None and published_identity is not None:
            _unlink_if_owned(final_path, published_identity)


def _revalidate_volume(
    inspector: WindowsVolumeInspector,
    directory: Path,
    expected_data_volume_id: str,
    expected_volume_id: str,
    expected_canonical_directory: Path,
):
    with inspector.open_directory(
        directory, expected_data_volume_id=expected_data_volume_id
    ) as current:
        if (
            current.identity.volume_id != expected_volume_id
            or str(current.identity.canonical_directory).casefold()
            != str(expected_canonical_directory).casefold()
        ):
            raise BackupPublicationError(
                "external volume changed during backup publication"
            )
        return current


def _file_identity(result: os.stat_result) -> tuple[int, int]:
    return result.st_dev, result.st_ino


def _unlink_if_owned(path: Path, owned_identity: tuple[int, int]) -> None:
    try:
        result = path.stat(follow_symlinks=False)
        if stat.S_ISREG(result.st_mode) and _file_identity(result) == owned_identity:
            path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        # A disconnected/unavailable drive must not turn cleanup into path guessing.
        return


def _create_owned_partial(path: Path) -> _OwnedPartial:
    if os.name != "nt":
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags, 0o600)
        identity = _file_identity(os.fstat(descriptor))
        return _OwnedPartial(path, os.fdopen(descriptor, "wb"), identity)

    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.DuplicateHandle.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    kernel32.DuplicateHandle.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.SetFileInformationByHandle.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    kernel32.SetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    cleanup_handle = kernel32.CreateFileW(
        str(path),
        0xC0010000,  # GENERIC_READ | GENERIC_WRITE | DELETE
        0x00000001 | 0x00000002 | 0x00000004,  # share read/write/delete
        None,
        1,  # CREATE_NEW
        0x80 | 0x00200000,  # FILE_ATTRIBUTE_NORMAL | OPEN_REPARSE_POINT
        None,
    )
    invalid = wintypes.HANDLE(-1).value
    if cleanup_handle == invalid:
        raise OSError(ctypes.get_last_error(), "partial backup could not be created")
    process = kernel32.GetCurrentProcess()
    stream_handle = wintypes.HANDLE()
    if not kernel32.DuplicateHandle(
        process, cleanup_handle, process, ctypes.byref(stream_handle), 0, False, 2
    ):
        error = ctypes.get_last_error()
        try:
            _mark_handle_for_deletion(kernel32, cleanup_handle)
        finally:
            kernel32.CloseHandle(cleanup_handle)
        raise OSError(error, "partial backup handle could not be prepared")
    try:
        descriptor = msvcrt.open_osfhandle(
            int(stream_handle.value), os.O_WRONLY | getattr(os, "O_BINARY", 0)
        )
    except OSError:
        kernel32.CloseHandle(stream_handle)
        try:
            _mark_handle_for_deletion(kernel32, cleanup_handle)
        finally:
            kernel32.CloseHandle(cleanup_handle)
        raise
    output = os.fdopen(descriptor, "wb")
    return _OwnedPartial(
        path=path,
        output=output,
        identity=_file_identity(os.fstat(descriptor)),
        cleanup_handle=cleanup_handle,
        kernel32=kernel32,
    )


def _mark_handle_for_deletion(kernel32: object, handle: object) -> None:
    import ctypes
    from ctypes import wintypes

    class _FileDispositionInfo(ctypes.Structure):
        _fields_ = [("DeleteFile", wintypes.BOOL)]

    disposition = _FileDispositionInfo(True)
    if not kernel32.SetFileInformationByHandle(
        handle, 4, ctypes.byref(disposition), ctypes.sizeof(disposition)
    ):
        raise OSError(ctypes.get_last_error(), "partial backup cleanup failed")


def _rename_no_replace(source: Path, destination: Path) -> None:
    if os.name == "nt":
        import ctypes

        move_file_ex = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
        move_file_ex.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        move_file_ex.restype = ctypes.c_int
        if not move_file_ex(str(source), str(destination), 0):
            code = ctypes.get_last_error()
            raise OSError(code, "backup publication rename failed")
        return
    # Hard-link creation is atomic and fails if destination already exists.
    os.link(source, destination)
    source.unlink()


@contextmanager
def _open_owned_for_read(partial: _OwnedPartial, path: Path):
    if partial.cleanup_handle is None or partial.kernel32 is None:
        with path.open("rb") as source:
            yield source
        return

    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = partial.kernel32
    process = kernel32.GetCurrentProcess()
    read_handle = wintypes.HANDLE()
    if not kernel32.DuplicateHandle(
        process,
        partial.cleanup_handle,
        process,
        ctypes.byref(read_handle),
        0,
        False,
        2,
    ):
        raise OSError(ctypes.get_last_error(), "backup verification handle failed")
    try:
        descriptor = msvcrt.open_osfhandle(
            int(read_handle.value), os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
    except OSError:
        kernel32.CloseHandle(read_handle)
        raise
    with os.fdopen(descriptor, "rb") as source:
        source.seek(0)
        yield source


def _sha256_file(path: Path, partial: _OwnedPartial) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with _open_owned_for_read(partial, path) as source:
        while chunk := source.read(_READ_CHUNK_BYTES):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()
