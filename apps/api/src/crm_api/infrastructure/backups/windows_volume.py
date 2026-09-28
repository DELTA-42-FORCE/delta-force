"""Handle-backed Windows volume inspection for external backup targets."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path, PureWindowsPath
import struct
from typing import Iterator, Protocol


class UnsafeBackupDestinationError(ValueError):
    """The selected destination is not a permitted backup volume."""


@dataclass(frozen=True, slots=True)
class VolumeIdentity:
    canonical_directory: Path
    volume_id: str
    filesystem: str
    is_removable: bool
    is_usb: bool


@dataclass(slots=True)
class ValidatedVolume:
    """A validated destination whose directory handle remains open in use."""

    handle: object
    identity: VolumeIdentity


class NativeVolumeApi(Protocol):
    def open_directory(self, path: Path) -> object: ...

    def close_handle(self, handle: object) -> None: ...

    def is_network_path(self, path: Path) -> bool: ...

    def has_reparse_component(self, path: Path) -> bool: ...

    def final_path(self, handle: object) -> str: ...

    def volume_info(self, canonical_path: str) -> dict[str, object]: ...


class WindowsVolumeInspector:
    """Reject unsafe destinations and retain a handle to the selected directory."""

    def __init__(self, native_api: NativeVolumeApi | None = None) -> None:
        self._native_api = native_api or _WindowsNativeVolumeApi()

    def identify_volume(self, directory: Path) -> VolumeIdentity:
        """Resolve a local data directory's volume without external-media policy."""
        api = self._native_api
        path = Path(directory)
        handle: object | None = None
        try:
            if api.is_network_path(path) or api.has_reparse_component(path):
                raise UnsafeBackupDestinationError(
                    "data volume path is not a safe local path"
                )
            handle = api.open_directory(path)
            canonical = api.final_path(handle)
            if api.is_network_path(Path(canonical)):
                raise UnsafeBackupDestinationError("data volume path is not local")
            return self._identity_from_info(canonical, api.volume_info(canonical))
        except UnsafeBackupDestinationError:
            raise
        except (OSError, KeyError, TypeError, ValueError):
            raise UnsafeBackupDestinationError(
                "data volume identity could not be resolved"
            ) from None
        finally:
            if handle is not None:
                api.close_handle(handle)

    @contextmanager
    def open_directory(
        self, directory: Path, *, expected_data_volume_id: str
    ) -> Iterator[ValidatedVolume]:
        api = self._native_api
        path = Path(directory)
        handle: object | None = None
        try:
            if api.is_network_path(path):
                raise UnsafeBackupDestinationError(
                    "backup destination is not a local external volume"
                )
            if api.has_reparse_component(path):
                raise UnsafeBackupDestinationError(
                    "backup destination contains a reparse point"
                )
            handle = api.open_directory(path)
            canonical = api.final_path(handle)
            if api.is_network_path(Path(canonical)):
                raise UnsafeBackupDestinationError(
                    "backup destination is not a local external volume"
                )
            identity = self._identity_from_info(canonical, api.volume_info(canonical))
            filesystem = identity.filesystem.strip().upper()
            if filesystem in {"FAT", "FAT32"}:
                raise UnsafeBackupDestinationError(
                    "backup destination filesystem is not supported"
                )
            if identity.volume_id == expected_data_volume_id:
                raise UnsafeBackupDestinationError(
                    "backup destination must differ from the data volume"
                )
            if not (identity.is_removable or identity.is_usb):
                raise UnsafeBackupDestinationError(
                    "backup destination is not removable or USB media"
                )
            yield ValidatedVolume(handle=handle, identity=identity)
        except UnsafeBackupDestinationError:
            raise
        except (OSError, KeyError, TypeError, ValueError):
            raise UnsafeBackupDestinationError(
                "backup destination could not be validated"
            ) from None
        finally:
            if handle is not None:
                api.close_handle(handle)

    @staticmethod
    def _identity_from_info(canonical: str, info: dict[str, object]) -> VolumeIdentity:
        return VolumeIdentity(
            canonical_directory=Path(canonical),
            volume_id=str(info["volume_id"]),
            filesystem=str(info["filesystem"]),
            is_removable=bool(info["is_removable"]),
            is_usb=bool(info["is_usb"]),
        )


class _WindowsNativeVolumeApi:
    """Small stdlib Win32 adapter, imported lazily for cross-platform policy tests."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Windows volume inspection is available only on Windows")
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._wintypes = wintypes
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateFileW.restype = wintypes.HANDLE
        self._kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
        self._kernel32.GetFinalPathNameByHandleW.argtypes = [
            wintypes.HANDLE,
            wintypes.LPWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        self._kernel32.GetDriveTypeW.restype = wintypes.UINT
        self._kernel32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
        self._kernel32.GetVolumeInformationW.restype = wintypes.BOOL
        self._kernel32.GetVolumeInformationW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.DWORD,
            self._ctypes.POINTER(wintypes.DWORD),
            self._ctypes.POINTER(wintypes.DWORD),
            self._ctypes.POINTER(wintypes.DWORD),
            wintypes.LPWSTR,
            wintypes.DWORD,
        ]
        self._kernel32.DeviceIoControl.restype = wintypes.BOOL
        self._kernel32.DeviceIoControl.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            self._ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        self._kernel32.GetFileInformationByHandleEx.restype = wintypes.BOOL
        self._kernel32.GetFileInformationByHandleEx.argtypes = [
            wintypes.HANDLE,
            self._ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]

    def open_directory(self, path: Path) -> object:
        flags = 0x02000000 | 0x00200000  # BACKUP_SEMANTICS | OPEN_REPARSE_POINT
        handle = self._kernel32.CreateFileW(
            str(path),
            0x0080,  # FILE_READ_ATTRIBUTES
            0x00000001 | 0x00000002 | 0x00000004,  # share read/write/delete
            None,
            3,  # OPEN_EXISTING
            flags,
            None,
        )
        invalid = self._wintypes.HANDLE(-1).value
        if handle == invalid:
            raise self._last_error("directory could not be opened")
        return handle

    def close_handle(self, handle: object) -> None:
        if not self._kernel32.CloseHandle(handle):
            raise self._last_error("directory handle could not be closed")

    def is_network_path(self, path: Path) -> bool:
        text = str(path)
        if text.casefold().startswith("\\\\?\\volume{"):
            return False
        return text.startswith(("\\\\", "//"))

    def has_reparse_component(self, path: Path) -> bool:
        from ctypes import wintypes

        windows_path = PureWindowsPath(str(path))
        if not windows_path.is_absolute():
            return True
        current = PureWindowsPath(windows_path.anchor)
        components = windows_path.parts[1:]
        for component in components:
            current /= component
            handle = self._kernel32.CreateFileW(
                str(current),
                0x0080,
                0x00000001 | 0x00000002 | 0x00000004,
                None,
                3,
                0x02000000 | 0x00200000,
                None,
            )
            if handle == wintypes.HANDLE(-1).value:
                raise self._last_error("path component could not be inspected")
            try:
                info = (wintypes.DWORD * 2)()
                if not self._kernel32.GetFileInformationByHandleEx(
                    handle, 9, self._ctypes.byref(info), self._ctypes.sizeof(info)
                ):
                    raise self._last_error("path component could not be inspected")
                if info[0] & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
                    return True
            finally:
                self._kernel32.CloseHandle(handle)
        return False

    def final_path(self, handle: object) -> str:
        size = 512
        while size <= 32768:
            buffer = self._ctypes.create_unicode_buffer(size)
            length = self._kernel32.GetFinalPathNameByHandleW(
                handle, buffer, size, 0x1  # VOLUME_NAME_GUID
            )
            if length == 0:
                raise self._last_error("destination volume could not be resolved")
            if length < size:
                return buffer.value
            size = length + 1
        raise OSError("destination path is too long")

    def volume_info(self, canonical_path: str) -> dict[str, object]:
        root = str(PureWindowsPath(canonical_path).anchor)
        if not root.startswith("\\\\?\\Volume{"):
            raise OSError("destination volume identity is unavailable")
        serial = self._wintypes.DWORD()
        max_component = self._wintypes.DWORD()
        flags = self._wintypes.DWORD()
        filesystem = self._ctypes.create_unicode_buffer(64)
        if not self._kernel32.GetVolumeInformationW(
            root,
            None,
            0,
            self._ctypes.byref(serial),
            self._ctypes.byref(max_component),
            self._ctypes.byref(flags),
            filesystem,
            len(filesystem),
        ):
            raise self._last_error("destination filesystem could not be inspected")
        drive_type = self._kernel32.GetDriveTypeW(root)
        device_properties = self._volume_device_properties(root)
        removable_devices = bool(device_properties) and all(
            is_removable for _, is_removable in device_properties
        )
        usb_devices = bool(device_properties) and all(
            bus_type == 7 for bus_type, _ in device_properties
        )
        return {
            "volume_id": root.casefold(),
            "filesystem": filesystem.value,
            "is_removable": drive_type == 2 or removable_devices,
            "is_usb": usb_devices,
        }

    def _volume_device_properties(
        self, volume_root: str
    ) -> tuple[tuple[int, bool], ...]:
        handle = self._kernel32.CreateFileW(
            volume_root,
            0,
            0x00000001 | 0x00000002,
            None,
            3,
            0,
            None,
        )
        if handle == self._wintypes.HANDLE(-1).value:
            return ()
        try:
            extent_output = (self._ctypes.c_ubyte * 4096)()
            returned = self._wintypes.DWORD()
            success = self._kernel32.DeviceIoControl(
                handle,
                0x00560000,  # IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS
                None,
                0,
                self._ctypes.byref(extent_output),
                len(extent_output),
                self._ctypes.byref(returned),
                None,
            )
            if not success:
                return ()
            try:
                disk_numbers = _disk_numbers_from_volume_extents(
                    bytes(extent_output[: returned.value])
                )
            except ValueError:
                return ()
            properties = tuple(
                self._physical_disk_properties(number) for number in disk_numbers
            )
            if any(properties_item is None for properties_item in properties):
                return ()
            return tuple(item for item in properties if item is not None)
        finally:
            self._kernel32.CloseHandle(handle)

    def _physical_disk_properties(self, disk_number: int) -> tuple[int, bool] | None:
        handle = self._kernel32.CreateFileW(
            rf"\\.\PhysicalDrive{disk_number}",
            0,
            0x00000001 | 0x00000002,
            None,
            3,
            0,
            None,
        )
        if handle == self._wintypes.HANDLE(-1).value:
            return None
        try:
            # STORAGE_PROPERTY_QUERY(DeviceProperty, StandardQuery, no extra bytes).
            query = (self._ctypes.c_ubyte * 12)(*([0] * 12))
            output = (self._ctypes.c_ubyte * 1024)()
            returned = self._wintypes.DWORD()
            success = self._kernel32.DeviceIoControl(
                handle,
                0x002D1400,  # IOCTL_STORAGE_QUERY_PROPERTY
                self._ctypes.byref(query),
                len(query),
                self._ctypes.byref(output),
                len(output),
                self._ctypes.byref(returned),
                None,
            )
            if not success or returned.value < 32:
                return None
            return _storage_device_properties(bytes(output[: returned.value]))
        finally:
            self._kernel32.CloseHandle(handle)

    def _last_error(self, message: str) -> OSError:
        code = self._ctypes.get_last_error()
        return OSError(code, message)


def _disk_numbers_from_volume_extents(output: bytes) -> tuple[int, ...]:
    if len(output) < 8:
        raise ValueError("volume extent response is truncated")
    count = int.from_bytes(output[:4], "little")
    extent_size = 24
    if count == 0 or len(output) < 8 + count * extent_size:
        raise ValueError("volume extent response is invalid")
    return tuple(
        struct.unpack_from("<I", output, 8 + index * extent_size)[0]
        for index in range(count)
    )


def _storage_bus_type_is_usb(descriptor: bytes) -> bool:
    properties = _storage_device_properties(descriptor)
    return properties is not None and properties[0] == 7


def _storage_device_properties(descriptor: bytes) -> tuple[int, bool] | None:
    if len(descriptor) < 32:
        return None
    bus_type = int.from_bytes(descriptor[28:32], "little")
    removable_media = descriptor[10] != 0
    return bus_type, removable_media
