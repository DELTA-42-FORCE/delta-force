from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
from pathlib import Path

import pytest

from crm_api.infrastructure.backups.publisher import (
    BackupPublicationError,
    estimate_encrypted_size,
    publish_backup_file,
)
from crm_api.infrastructure.backups.container import (
    FRAME_SIZE_BYTES,
    encrypt_payload_to_stream,
)
from crm_api.infrastructure.backups.windows_volume import (
    UnsafeBackupDestinationError,
    VolumeIdentity,
    ValidatedVolume,
)


@dataclass
class FakeInspector:
    canonical_directory: Path
    volume_ids: tuple[str, ...] = ("usb-volume", "usb-volume", "usb-volume")
    calls: int = 0

    @contextmanager
    def open_directory(self, directory, *, expected_data_volume_id):
        del directory
        current = self.volume_ids[min(self.calls, len(self.volume_ids) - 1)]
        self.calls += 1
        if current == expected_data_volume_id:
            raise UnsafeBackupDestinationError("same volume")
        yield ValidatedVolume(
            handle=object(),
            identity=VolumeIdentity(
                canonical_directory=self.canonical_directory,
                volume_id=current,
                filesystem="NTFS",
                is_removable=False,
                is_usb=True,
            ),
        )


def run_publish(directory, inspector, payload=b"synthetic backup", writer=None):
    payload_path = directory / ".synthetic-payload.tar"
    payload_path.write_bytes(payload)

    def encrypt(stream):
        encrypt_payload_to_stream(
            payload_path=payload_path,
            output=stream,
            passphrase="synthetic passphrase",
            app_version="0.1.0",
            created_at="2026-09-28T12:00:00Z",
            schema_revision="synthetic-revision",
        )

    try:
        return publish_backup_file(
            payload_bytes=len(payload),
            destination_directory=directory,
            expected_data_volume_id="system-volume",
            inspector=inspector,
            write_encrypted_partial=writer or encrypt,
        )
    finally:
        payload_path.unlink(missing_ok=True)


def test_encrypted_size_bound_accounts_for_header_and_each_frame():
    one_frame_size = 12 + 4096 + 1 + 20
    two_frame_size = 12 + 4096 + FRAME_SIZE_BYTES + 1 + 40

    assert estimate_encrypted_size(1) == one_frame_size
    assert estimate_encrypted_size(FRAME_SIZE_BYTES + 1) == two_frame_size


@pytest.mark.parametrize("payload_bytes", [0, -1, True, "1"])
def test_encrypted_size_rejects_invalid_payload_lengths(payload_bytes):
    with pytest.raises(BackupPublicationError):
        estimate_encrypted_size(payload_bytes)


def test_publishes_and_returns_only_name_size_digest_and_opaque_volume(tmp_path):
    inspector = FakeInspector(tmp_path)

    result = run_publish(tmp_path, inspector)

    published = tmp_path / result.filename
    contents = published.read_bytes()
    assert contents.startswith(b"DFCRMBK1")
    assert result.size_bytes == len(contents)
    assert result.sha256 == hashlib.sha256(contents).hexdigest()
    assert result.volume_id == "usb-volume"
    assert "tmp" not in result.filename
    assert list(tmp_path.glob("*.partial")) == []


def test_rejects_insufficient_space_before_creating_partial(tmp_path, monkeypatch):
    import shutil

    usage = shutil._ntuple_diskusage(total=1024, used=900, free=124)
    monkeypatch.setattr(
        "crm_api.infrastructure.backups.publisher.shutil.disk_usage",
        lambda _path: usage,
    )
    inspector = FakeInspector(tmp_path)

    with pytest.raises(BackupPublicationError, match="free space"):
        run_publish(tmp_path, inspector)

    assert list(tmp_path.iterdir()) == []


def test_collision_never_overwrites_existing_final_file(tmp_path, monkeypatch):
    import crm_api.infrastructure.backups.publisher as publisher

    filename_token = "a" * 32
    monkeypatch.setattr(publisher.secrets, "token_hex", lambda _n: filename_token)
    existing = tmp_path / f"backup-{filename_token}.dfcrmbak"
    existing.write_bytes(b"pre-existing")

    with pytest.raises(BackupPublicationError):
        run_publish(tmp_path, FakeInspector(tmp_path))

    assert existing.read_bytes() == b"pre-existing"
    assert list(tmp_path.glob("*.partial")) == []


def test_cleans_only_owned_partial_when_writer_fails(tmp_path):
    unrelated = tmp_path / "user-data.partial"
    unrelated.write_bytes(b"preserve")

    def fail_after_write(stream):
        stream.write(b"partial")
        raise OSError("synthetic disk failure")

    with pytest.raises(BackupPublicationError):
        run_publish(tmp_path, FakeInspector(tmp_path), writer=fail_after_write)

    assert unrelated.read_bytes() == b"preserve"
    assert list(tmp_path.glob(".delta-force-*.partial")) == []


def test_does_not_delete_a_partial_path_replaced_by_another_file(tmp_path):
    replacement = b"another process owns this file now"

    def replace_owned_path(stream):
        stream.write(b"original partial contents")
        partial = next(tmp_path.glob(".delta-force-*.partial"))
        partial.unlink()
        partial.write_bytes(replacement)

    with pytest.raises(BackupPublicationError, match="identity changed"):
        run_publish(
            tmp_path,
            FakeInspector(tmp_path),
            writer=replace_owned_path,
        )

    partial = next(tmp_path.glob(".delta-force-*.partial"))
    assert partial.read_bytes() == replacement


def test_revalidates_volume_before_publishing_and_cleans_partial(tmp_path):
    inspector = FakeInspector(tmp_path, volume_ids=("usb-volume", "replacement-volume"))

    with pytest.raises(BackupPublicationError, match="volume changed"):
        run_publish(tmp_path, inspector)

    assert list(tmp_path.iterdir()) == []


def test_digest_verification_failure_does_not_leave_final_backup(tmp_path, monkeypatch):
    import crm_api.infrastructure.backups.publisher as publisher

    original_hash = publisher._sha256_file
    calls = 0

    def corrupt_second_digest(path, owned_partial):
        nonlocal calls
        calls += 1
        size, digest = original_hash(path, owned_partial)
        return size, digest if calls == 1 else "0" * 64

    monkeypatch.setattr(publisher, "_sha256_file", corrupt_second_digest)

    with pytest.raises(BackupPublicationError, match="verification"):
        run_publish(tmp_path, FakeInspector(tmp_path))

    assert list(tmp_path.glob("*.dfcrmbak")) == []
    assert list(tmp_path.glob("*.partial")) == []
