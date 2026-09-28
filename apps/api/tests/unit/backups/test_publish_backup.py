from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
import pytest

import crm_api.application.backups.publish_backup as use_case
from crm_api.infrastructure.backups.publisher import PublishedBackup


@dataclass
class FakeInspector:
    pass


@contextmanager
def fake_snapshot(payload_path, cleaned):
    payload_path.write_bytes(b"synthetic snapshot tar")
    try:
        yield type(
            "Payload",
            (),
            {"path": payload_path, "schema_revision": "revision-1"},
        )()
    finally:
        payload_path.unlink(missing_ok=True)
        cleaned.append(True)


@pytest.mark.parametrize("publisher_fails", [False, True])
def test_composes_snapshot_encryption_and_publisher_and_cleans_plaintext(
    tmp_path, monkeypatch, publisher_fails
):
    payload_path = tmp_path / "payload.tar"
    cleaned = []
    captured = {}

    @contextmanager
    def build_backup_payload(*, database_path, documents_root, temporary_root):
        captured["snapshot_args"] = (database_path, documents_root, temporary_root)
        with fake_snapshot(payload_path, cleaned) as payload:
            yield payload

    def publish_backup_file(**kwargs):
        captured["payload_bytes"] = kwargs["payload_bytes"]
        captured["destination_directory"] = kwargs["destination_directory"]
        kwargs["write_encrypted_partial"](captured.setdefault("output", BytesIO()))
        if publisher_fails:
            raise ValueError("synthetic publication failure")
        return PublishedBackup(
            filename="backup-synthetic.dfcrmbak",
            size_bytes=len(captured["output"].getvalue()),
            sha256="synthetic-digest",
            volume_id="usb-volume",
        )

    def encrypt_payload_to_stream(**kwargs):
        captured["encryption_args"] = kwargs
        kwargs["output"].write(b"encrypted synthetic backup")

    monkeypatch.setattr(use_case.snapshot, "build_backup_payload", build_backup_payload)
    monkeypatch.setattr(use_case.publisher, "publish_backup_file", publish_backup_file)
    monkeypatch.setattr(
        use_case.container, "encrypt_payload_to_stream", encrypt_payload_to_stream
    )

    def call():
        return use_case.publish_backup(
            database_path=tmp_path / "crm.sqlite3",
            documents_root=tmp_path / "documents",
            temporary_root=tmp_path / "private-tmp",
            destination_directory=tmp_path / "external-drive",
            passphrase="synthetic passphrase",
            app_version="0.1.0",
            created_at="2026-09-28T12:00:00Z",
            data_volume_id="system-volume",
            inspector=FakeInspector(),
        )

    if publisher_fails:
        with pytest.raises(use_case.BackupPublicationError):
            call()
    else:
        result = call()
        assert result.filename == "backup-synthetic.dfcrmbak"

    assert captured["payload_bytes"] == len(b"synthetic snapshot tar")
    assert captured["encryption_args"]["passphrase"] == "synthetic passphrase"
    assert captured["encryption_args"]["schema_revision"] == "revision-1"
    assert captured["output"].getvalue() == b"encrypted synthetic backup"
    assert cleaned == [True]
    assert not payload_path.exists()
