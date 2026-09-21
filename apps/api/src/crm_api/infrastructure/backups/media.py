"""Validação do HD externo sem confiar apenas no texto do caminho."""

from __future__ import annotations

import ctypes
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import struct
from typing import BinaryIO, Iterator


class BackupMediaError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class VerifiedBackupMedia:
    directory: Path
    identity: str
    volume_serial: int | None = None


@dataclass(frozen=True, slots=True)
class BackupMediaPolicy:
    """Aceita somente mídia externa; o bypass existe só para desenvolvimento/teste."""

    data_root: Path
    allow_local_destination: bool = False

    def validate_directory(self, value: str | Path) -> VerifiedBackupMedia:
        directory = _existing_plain_directory(value)
        if self.allow_local_destination:
            return VerifiedBackupMedia(
                directory=directory,
                identity=f"development:{directory.anchor or directory}",
                volume_serial=None,
            )
        if os.name != "nt":
            raise BackupMediaError("external backup media requires Windows")
        destination_serial = _verify_windows_directory_handle(directory)
        destination = _windows_volume(directory)
        if destination_serial != destination.volume_serial:
            raise BackupMediaError("backup destination volume identity changed")
        source_directory = _existing_plain_directory(self.data_root)
        source_serial = _verify_windows_directory_handle(source_directory)
        source = _windows_volume(source_directory)
        if source_serial != source.volume_serial:
            raise BackupMediaError("local data volume identity changed")
        if destination.identity == source.identity:
            raise BackupMediaError("backup destination must use another volume")
        if destination.filesystem in {"FAT", "FAT32"}:
            raise BackupMediaError("FAT/FAT32 cannot safely store CRM backups")
        if not destination.external:
            raise BackupMediaError("backup destination is not an external drive")
        return VerifiedBackupMedia(
            directory=directory,
            identity=destination.identity,
            volume_serial=destination.volume_serial,
        )

    def validate_source_file(
        self, value: str | Path
    ) -> tuple[Path, VerifiedBackupMedia]:
        _reject_remote_or_device_path(value)
        source = Path(value)
        if not source.is_absolute() or not source.exists() or not source.is_file():
            raise BackupMediaError("backup file does not exist")
        _reject_reparse_chain(source)
        resolved = source.resolve(strict=True)
        media = self.validate_directory(resolved.parent)
        return resolved, media

    def revalidate(self, media: VerifiedBackupMedia) -> None:
        current = self.validate_directory(media.directory)
        if current.identity != media.identity:
            raise BackupMediaError("backup drive identity changed during the operation")

    def fingerprint_file(
        self, value: str | Path, *, media: VerifiedBackupMedia
    ) -> tuple[int, str]:
        """Reabre por handle e comprova volume, caminho, tamanho e SHA-256."""
        _reject_remote_or_device_path(value)
        path = Path(value)
        _reject_reparse_chain(path)
        resolved = path.resolve(strict=True)
        if resolved.parent != media.directory:
            raise BackupMediaError("backup file escaped the validated directory")
        digest = hashlib.sha256()
        total = 0
        with _open_regular_file_by_handle(resolved) as (handle, volume_serial):
            if (
                media.volume_serial is not None
                and volume_serial is not None
                and volume_serial != media.volume_serial
            ):
                raise BackupMediaError("backup file is on another volume")
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                total += len(chunk)
        self.revalidate(media)
        return total, digest.hexdigest()

    def copy_file_to(
        self,
        value: str | Path,
        *,
        media: VerifiedBackupMedia,
        destination: Path,
    ) -> tuple[int, str]:
        """Copia de um único handle validado para staging local exclusivo."""
        _reject_remote_or_device_path(value)
        path = Path(value)
        _reject_reparse_chain(path)
        resolved = path.resolve(strict=True)
        if resolved.parent != media.directory:
            raise BackupMediaError("backup file escaped the validated directory")
        output_flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
        try:
            output_descriptor = os.open(destination, output_flags, 0o600)
        except OSError as error:
            raise BackupMediaError("restore staging file cannot be created") from error
        digest = hashlib.sha256()
        total = 0
        try:
            with (
                _open_regular_file_by_handle(resolved) as (source, volume_serial),
                os.fdopen(output_descriptor, "wb") as output,
            ):
                output_descriptor = -1
                if (
                    media.volume_serial is not None
                    and volume_serial is not None
                    and volume_serial != media.volume_serial
                ):
                    raise BackupMediaError("backup file is on another volume")
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
                    total += len(chunk)
                output.flush()
                os.fsync(output.fileno())
            self.revalidate(media)
            return total, digest.hexdigest()
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        finally:
            if output_descriptor >= 0:
                os.close(output_descriptor)


@dataclass(frozen=True, slots=True)
class _WindowsVolume:
    identity: str
    filesystem: str
    external: bool
    volume_serial: int


def _existing_plain_directory(value: str | Path) -> Path:
    _reject_remote_or_device_path(value)
    raw = Path(value)
    if not raw.is_absolute() or not raw.exists() or not raw.is_dir():
        raise BackupMediaError("backup directory does not exist")
    _reject_reparse_chain(raw)
    return raw.resolve(strict=True)


def _reject_remote_or_device_path(value: str | Path) -> None:
    """Rejeita namespaces remotos/dispositivo antes de qualquer acesso ao disco."""
    raw = os.fspath(value)
    if not isinstance(raw, str):
        raise BackupMediaError("backup path is invalid")
    windows_form = raw.replace("/", "\\")
    upper = windows_form.upper()
    if (
        windows_form.startswith("\\\\")
        or windows_form.startswith("\\??\\")
        or upper.startswith("\\DEVICE\\")
        or upper.startswith("\\GLOBALROOT\\")
    ):
        raise BackupMediaError("network and device paths are not allowed")


def _reject_reparse_chain(path: Path) -> None:
    current = path
    while True:
        try:
            metadata = current.lstat()
        except OSError as error:
            raise BackupMediaError("backup path cannot be inspected") from error
        attributes = getattr(metadata, "st_file_attributes", 0)
        reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if stat.S_ISLNK(metadata.st_mode) or attributes & reparse_attribute:
            raise BackupMediaError("backup path cannot contain links or reparse points")
        if current.parent == current:
            return
        current = current.parent


def _windows_volume(path: Path) -> _WindowsVolume:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetVolumePathNameW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    kernel32.GetVolumePathNameW.restype = wintypes.BOOL
    kernel32.GetVolumeInformationW.restype = wintypes.BOOL
    kernel32.GetVolumeNameForVolumeMountPointW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    kernel32.GetVolumeNameForVolumeMountPointW.restype = wintypes.BOOL
    kernel32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetDriveTypeW.restype = wintypes.UINT
    volume_path = ctypes.create_unicode_buffer(261)
    if not kernel32.GetVolumePathNameW(str(path), volume_path, len(volume_path)):
        raise BackupMediaError("backup volume cannot be resolved")
    mount_point = volume_path.value
    if mount_point.startswith("\\\\"):
        raise BackupMediaError("network destinations are not allowed")

    filesystem = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD()
    if not kernel32.GetVolumeInformationW(
        mount_point,
        None,
        0,
        ctypes.byref(serial),
        None,
        None,
        filesystem,
        len(filesystem),
    ):
        raise BackupMediaError("backup volume information is unavailable")

    volume_name = ctypes.create_unicode_buffer(261)
    if kernel32.GetVolumeNameForVolumeMountPointW(
        mount_point, volume_name, len(volume_name)
    ):
        identity = volume_name.value.lower()
    else:
        identity = f"serial:{serial.value:08x}"

    drive_type = kernel32.GetDriveTypeW(mount_point)
    drive_removable = 2
    drive_fixed = 3
    if drive_type not in {drive_removable, drive_fixed}:
        raise BackupMediaError("backup destination drive type is not supported")
    external = drive_type == drive_removable or _windows_bus_is_usb(mount_point)
    return _WindowsVolume(
        identity=identity,
        filesystem=filesystem.value.upper(),
        external=external,
        volume_serial=serial.value,
    )


@contextmanager
def _open_regular_file_by_handle(
    path: Path,
) -> Iterator[tuple[BinaryIO, int | None]]:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if os.name != "nt" and hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise BackupMediaError("backup file cannot be opened safely") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise BackupMediaError("backup file is not regular")
        volume_serial = (
            _verify_windows_file_handle(descriptor, path) if os.name == "nt" else None
        )
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            yield handle, volume_serial
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _verify_windows_file_handle(descriptor: int, expected_path: Path) -> int:
    import msvcrt

    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetFileInformationByHandle.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ByHandleFileInformation),
    ]
    kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.GetFinalPathNameByHandleW.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    handle = wintypes.HANDLE(msvcrt.get_osfhandle(descriptor))
    information = _ByHandleFileInformation()
    if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(information)):
        raise BackupMediaError("backup file identity is unavailable")
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if information.dwFileAttributes & reparse_attribute:
        raise BackupMediaError("backup file cannot be a reparse point")
    buffer = ctypes.create_unicode_buffer(32_768)
    length = kernel32.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
    if length == 0 or length >= len(buffer):
        raise BackupMediaError("backup file final path is unavailable")
    final_path = buffer.value
    if final_path.startswith("\\\\?\\UNC\\"):
        raise BackupMediaError("network backup files are not allowed")
    if final_path.startswith("\\\\?\\"):
        final_path = final_path[4:]
    if os.path.normcase(os.path.abspath(final_path)) != os.path.normcase(
        os.path.abspath(expected_path)
    ):
        raise BackupMediaError("backup file handle resolved to another path")
    return int(information.dwVolumeSerialNumber)


def _verify_windows_directory_handle(expected_path: Path) -> int:
    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.GetFileInformationByHandle.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ByHandleFileInformation),
    ]
    kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.GetFinalPathNameByHandleW.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.CreateFileW(
        str(expected_path),
        0,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x02000000 | 0x00200000,
        None,
    )
    invalid_handle = wintypes.HANDLE(-1).value
    if handle == invalid_handle:
        raise BackupMediaError("backup directory cannot be opened by handle")
    try:
        information = _ByHandleFileInformation()
        if not kernel32.GetFileInformationByHandle(
            wintypes.HANDLE(handle), ctypes.byref(information)
        ):
            raise BackupMediaError("backup directory identity is unavailable")
        reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if information.dwFileAttributes & reparse_attribute:
            raise BackupMediaError("backup directory cannot be a reparse point")
        buffer = ctypes.create_unicode_buffer(32_768)
        length = kernel32.GetFinalPathNameByHandleW(
            wintypes.HANDLE(handle), buffer, len(buffer), 0
        )
        if length == 0 or length >= len(buffer):
            raise BackupMediaError("backup directory final path is unavailable")
        final_path = buffer.value
        if final_path.startswith("\\\\?\\UNC\\"):
            raise BackupMediaError("network backup directories are not allowed")
        if final_path.startswith("\\\\?\\"):
            final_path = final_path[4:]
        if os.path.normcase(os.path.abspath(final_path)) != os.path.normcase(
            os.path.abspath(expected_path)
        ):
            raise BackupMediaError("backup directory handle resolved elsewhere")
        return int(information.dwVolumeSerialNumber)
    finally:
        kernel32.CloseHandle(wintypes.HANDLE(handle))


def _windows_bus_is_usb(mount_point: str) -> bool:
    """Consulta o descritor do volume; discos USB costumam aparecer como FIXED."""
    drive = mount_point.rstrip("\\")
    if len(drive) != 2 or drive[1] != ":":
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.DeviceIoControl.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    kernel32.DeviceIoControl.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.CreateFileW(
        f"\\\\.\\{drive}",
        0,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0,
        None,
    )
    invalid_handle = wintypes.HANDLE(-1).value
    if handle == invalid_handle:
        return False
    try:
        query = struct.pack("<II4x", 0, 0)
        output = ctypes.create_string_buffer(1024)
        returned = wintypes.DWORD()
        ok = kernel32.DeviceIoControl(
            wintypes.HANDLE(handle),
            0x002D1400,
            query,
            len(query),
            output,
            len(output),
            ctypes.byref(returned),
            None,
        )
        if not ok or returned.value < 32:
            return False
        (bus_type,) = struct.unpack_from("<I", output.raw, 28)
        return bus_type == 7
    finally:
        kernel32.CloseHandle(wintypes.HANDLE(handle))
