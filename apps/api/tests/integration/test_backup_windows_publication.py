"""Windows-only integration proof for native volume inspection and rename."""

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path

import pytest

from crm_api.infrastructure.backups.publisher import publish_backup_file
from crm_api.infrastructure.backups.publisher import (
    _open_owned_for_read,
    _create_owned_partial,
    _file_identity,
    _rename_no_replace,
)
from crm_api.infrastructure.backups.container import (
    encrypt_payload_to_stream,
    read_backup_header,
)
from crm_api.infrastructure.backups.windows_volume import (
    ValidatedVolume,
    VolumeIdentity,
    _WindowsNativeVolumeApi,
)

pytestmark = pytest.mark.skipif(os.name != "nt", reason="requires native Windows APIs")


def test_windows_owned_partial_can_be_written_and_atomically_renamed(
    tmp_path: Path,
) -> None:
    partial_path = tmp_path / ".synthetic-backup.partial"
    final_path = tmp_path / "synthetic-backup.dfcrmbak"
    owned = _create_owned_partial(partial_path)
    committed = False
    try:
        owned.output.write(b"synthetic encrypted bytes")
        owned.output.flush()
        os.fsync(owned.output.fileno())
        assert (
            _file_identity(partial_path.stat(follow_symlinks=False)) == owned.identity
        )
        owned.output.close()

        _rename_no_replace(partial_path, final_path)

        assert not partial_path.exists()
        assert _file_identity(final_path.stat(follow_symlinks=False)) == owned.identity
        with _open_owned_for_read(owned, final_path) as source:
            assert source.read() == b"synthetic encrypted bytes"
        owned.finish(committed=True)
        committed = True
    finally:
        if not committed:
            owned.finish(committed=False)


def test_windows_handle_resolves_local_ntfs_temp_volume(tmp_path: Path) -> None:
    native = _WindowsNativeVolumeApi()
    handle = native.open_directory(tmp_path)
    try:
        canonical = native.final_path(handle)
        info = native.volume_info(canonical)
    finally:
        native.close_handle(handle)

    assert canonical.casefold().startswith("\\\\?\\volume{")
    assert info["volume_id"]
    assert info["filesystem"]


def test_windows_movefileex_publishes_and_verifies_synthetic_bytes(
    tmp_path: Path,
) -> None:
    class TestInspector:
        @contextmanager
        def open_directory(self, directory, *, expected_data_volume_id):
            assert directory == tmp_path
            assert expected_data_volume_id == "system-volume"
            yield ValidatedVolume(
                handle=object(),
                identity=VolumeIdentity(
                    canonical_directory=tmp_path,
                    volume_id="synthetic-usb-identity",
                    filesystem="NTFS",
                    is_removable=False,
                    is_usb=True,
                ),
            )

    content = b"synthetic plaintext backup payload"
    payload_path = tmp_path / "synthetic-payload.tar"
    payload_path.write_bytes(content)
    try:
        result = publish_backup_file(
            payload_bytes=len(content),
            destination_directory=tmp_path,
            expected_data_volume_id="system-volume",
            inspector=TestInspector(),
            write_encrypted_partial=lambda stream: encrypt_payload_to_stream(
                payload_path=payload_path,
                output=stream,
                passphrase="synthetic passphrase",
                app_version="0.1.0",
                created_at="2026-09-28T12:00:00Z",
                schema_revision="synthetic-revision",
            ),
        )
    finally:
        payload_path.unlink(missing_ok=True)

    published = tmp_path / result.filename
    encrypted = published.read_bytes()
    assert read_backup_header(published).payload_bytes == len(content)
    assert result.size_bytes == len(encrypted)
    assert result.sha256 == hashlib.sha256(encrypted).hexdigest()
    assert list(tmp_path.glob("*.partial")) == []
