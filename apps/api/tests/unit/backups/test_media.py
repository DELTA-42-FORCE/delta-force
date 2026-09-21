import os
from pathlib import Path

import pytest

from crm_api.infrastructure.backups import media
from crm_api.infrastructure.backups.media import BackupMediaError, BackupMediaPolicy


@pytest.mark.parametrize(
    "remote_path",
    [
        r"\\server\share\backups",
        r"\\?\UNC\server\share\backups",
        r"\\.\C:\backups",
        r"\??\C:\backups",
        r"\Device\HarddiskVolume1\backups",
    ],
)
def test_destination_rejects_remote_and_device_paths_before_filesystem_io(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    remote_path: str,
) -> None:
    policy = BackupMediaPolicy(data_root=tmp_path, allow_local_destination=True)
    monkeypatch.setattr(
        media,
        "Path",
        lambda value: pytest.fail(f"filesystem path constructed for {value}"),
    )

    with pytest.raises(BackupMediaError, match="network and device"):
        policy.validate_directory(remote_path)


def test_source_rejects_unc_before_filesystem_io(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    policy = BackupMediaPolicy(data_root=tmp_path, allow_local_destination=True)
    monkeypatch.setattr(
        media,
        "Path",
        lambda value: pytest.fail(f"filesystem path constructed for {value}"),
    )

    with pytest.raises(BackupMediaError, match="network and device"):
        policy.validate_source_file(r"\\server\share\backup.dfcrmbak")


@pytest.mark.skipif(os.name != "nt", reason="Windows handle validation")
def test_directory_identity_is_read_from_the_open_handle(tmp_path: Path) -> None:
    serial = media._verify_windows_directory_handle(tmp_path.resolve())

    assert isinstance(serial, int)
    assert serial >= 0
