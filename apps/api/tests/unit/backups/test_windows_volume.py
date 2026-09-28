from pathlib import Path

import pytest

from crm_api.infrastructure.backups.windows_volume import (
    UnsafeBackupDestinationError,
    WindowsVolumeInspector,
    _disk_numbers_from_volume_extents,
    _storage_bus_type_is_usb,
    _storage_device_properties,
)


class FakeNativeVolumeApi:
    def __init__(self, volumes, *, network=False, reparse=()):
        self.volumes = volumes
        self.network = network
        self.reparse = set(reparse)
        self.closed = []

    def open_directory(self, path):
        return str(path)

    def close_handle(self, handle):
        self.closed.append(handle)

    def is_network_path(self, path):
        text = str(path)
        return self.network or (
            text.startswith("\\\\") and not text.casefold().startswith("\\\\?\\volume{")
        )

    def has_reparse_component(self, path):
        return str(path) in self.reparse

    def final_path(self, handle):
        return self.volumes[handle]["canonical"]

    def volume_info(self, canonical_path):
        return self.volumes[
            next(
                key
                for key, value in self.volumes.items()
                if value["canonical"] == canonical_path
            )
        ]


def volume(
    canonical, *, volume_id="volume-a", filesystem="NTFS", removable=False, usb=False
):
    return {
        "canonical": canonical,
        "volume_id": volume_id,
        "filesystem": filesystem,
        "is_removable": removable,
        "is_usb": usb,
    }


def test_accepts_removable_volume_and_keeps_handle_open_until_context_exit():
    directory = Path("E:/backups")
    api = FakeNativeVolumeApi(
        {str(directory): volume("\\\\?\\Volume{backup}\\backups", removable=True)}
    )
    inspector = WindowsVolumeInspector(native_api=api)

    with inspector.open_directory(
        directory, expected_data_volume_id="system-volume"
    ) as selected:
        assert selected.identity.volume_id == "volume-a"
        assert selected.identity.is_removable is True
        assert api.closed == []

    assert api.closed == [str(directory)]


def test_accepts_usb_fixed_volume():
    directory = Path("E:/backups")
    api = FakeNativeVolumeApi(
        {str(directory): volume("\\\\?\\Volume{backup}\\backups", usb=True)}
    )

    with WindowsVolumeInspector(native_api=api).open_directory(
        directory, expected_data_volume_id="system-volume"
    ) as selected:
        assert selected.identity.is_usb is True


def test_identifies_local_data_volume_without_requiring_external_media():
    directory = Path("C:/Users/owner/AppData/Local/DeltaForce")
    api = FakeNativeVolumeApi(
        {
            str(directory): volume(
                "\\\\?\\Volume{system}\\Users\\owner\\AppData\\Local\\DeltaForce",
                volume_id="system-volume",
            )
        }
    )

    identity = WindowsVolumeInspector(native_api=api).identify_volume(directory)

    assert identity.volume_id == "system-volume"
    assert identity.is_removable is False
    assert api.closed == [str(directory)]


@pytest.mark.parametrize(
    "directory,metadata,kwargs",
    [
        ("\\\\server\\share", None, {"network": True}),
        (
            "Z:/mapped-network-share",
            volume("\\\\?\\UNC\\server\\share"),
            {},
        ),
        (
            "E:/cloud",
            volume("\\\\?\\Volume{cloud}\\cloud"),
            {"reparse": ("E:/cloud",)},
        ),
        ("E:/fat", volume("\\\\?\\Volume{fat}\\fat", filesystem="FAT"), {}),
        ("E:/fat32", volume("\\\\?\\Volume{fat32}\\fat32", filesystem="FAT32"), {}),
        (
            "E:/same-data",
            volume(
                "\\\\?\\Volume{system}\\same-data",
                volume_id="system-volume",
                removable=True,
            ),
            {},
        ),
        ("E:/fixed", volume("\\\\?\\Volume{fixed}\\fixed"), {}),
    ],
)
def test_rejects_unsafe_destinations(directory, metadata, kwargs):
    volumes = {} if metadata is None else {directory: metadata}
    api = FakeNativeVolumeApi(volumes, **kwargs)

    with pytest.raises(UnsafeBackupDestinationError):
        with WindowsVolumeInspector(native_api=api).open_directory(
            Path(directory), expected_data_volume_id="system-volume"
        ):
            pytest.fail("unsafe volume was accepted")


def test_rejects_reparse_component_even_when_final_volume_is_safe():
    directory = "E:/junction/backup"
    api = FakeNativeVolumeApi(
        {directory: volume("\\\\?\\Volume{backup}\\backup")},
        reparse=(directory,),
    )

    with pytest.raises(UnsafeBackupDestinationError):
        with WindowsVolumeInspector(native_api=api).open_directory(
            Path(directory), expected_data_volume_id="system-volume"
        ):
            pytest.fail("reparse destination was accepted")


def test_parses_volume_disk_extents_for_usb_fixed_drive_decision():
    extent_header = (2).to_bytes(4, "little") + b"\0" * 4
    first = (3).to_bytes(4, "little") + b"\0" * 20
    second = (7).to_bytes(4, "little") + b"\0" * 20

    assert _disk_numbers_from_volume_extents(extent_header + first + second) == (3, 7)


def test_rejects_malformed_volume_extents_and_requires_usb_bus_type():
    with pytest.raises(ValueError):
        _disk_numbers_from_volume_extents(b"\x01\0\0\0")

    usb_descriptor = bytearray(32)
    usb_descriptor[28:32] = (7).to_bytes(4, "little")
    usb_descriptor[10] = 1
    sata_descriptor = bytearray(32)
    sata_descriptor[28:32] = (11).to_bytes(4, "little")

    assert _storage_bus_type_is_usb(bytes(usb_descriptor)) is True
    assert _storage_bus_type_is_usb(bytes(sata_descriptor)) is False
    assert _storage_bus_type_is_usb(b"short") is False
    assert _storage_device_properties(bytes(usb_descriptor)) == (7, True)
