import json
from pathlib import Path
import struct

import pytest

from crm_api.infrastructure.backups.container import (
    BackupPasswordOrIntegrityError,
    InvalidBackupFormatError,
    decrypt_payload,
    encrypt_payload,
    read_backup_header,
)

_PREFIX = struct.Struct(">8sI")


def _encrypt(tmp_path: Path, content: bytes = b"conteudo sintetico") -> Path:
    payload = tmp_path / "payload.tar"
    payload.write_bytes(content)
    destination = tmp_path / "backup.partial"
    encrypt_payload(
        payload_path=payload,
        destination_path=destination,
        passphrase="senha sintetica forte",
        app_version="0.1.0",
        created_at="2026-09-19T20:00:00Z",
        schema_revision="synthetic_revision",
    )
    return destination


def test_container_round_trip_uses_bounded_public_header(tmp_path: Path) -> None:
    source = _encrypt(tmp_path, b"abc" * 400_000)
    restored = tmp_path / "restored.tar"

    header = read_backup_header(source)
    decrypt_payload(
        source_path=source,
        destination_path=restored,
        passphrase="senha sintetica forte",
    )

    assert header.frame_count == 2
    assert header.payload_bytes == 1_200_000
    assert header.schema_revision == "synthetic_revision"
    assert restored.read_bytes() == b"abc" * 400_000
    assert b"senha sintetica forte" not in source.read_bytes()


def test_wrong_password_or_tampering_never_leaves_plaintext(tmp_path: Path) -> None:
    source = _encrypt(tmp_path)
    restored = tmp_path / "restored.tar"

    with pytest.raises(BackupPasswordOrIntegrityError):
        decrypt_payload(
            source_path=source,
            destination_path=restored,
            passphrase="outra senha sintetica",
        )

    assert not restored.exists()

    changed = bytearray(source.read_bytes())
    changed[-1] ^= 1
    source.write_bytes(changed)
    with pytest.raises(BackupPasswordOrIntegrityError):
        decrypt_payload(
            source_path=source,
            destination_path=restored,
            passphrase="senha sintetica forte",
        )
    assert not restored.exists()


@pytest.mark.parametrize("mutation", ["truncate", "append"])
def test_container_rejects_missing_or_extra_bytes_before_kdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    source = _encrypt(tmp_path)
    content = source.read_bytes()
    source.write_bytes(content[:-1] if mutation == "truncate" else content + b"x")
    monkeypatch.setattr(
        "crm_api.infrastructure.backups.container.hashlib.scrypt",
        lambda *args, **kwargs: pytest.fail("KDF must not run"),
    )

    with pytest.raises(InvalidBackupFormatError):
        decrypt_payload(
            source_path=source,
            destination_path=tmp_path / "restored.tar",
            passphrase="senha sintetica forte",
        )


def test_untrusted_kdf_parameters_are_rejected_before_kdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _encrypt(tmp_path)
    content = source.read_bytes()
    magic, header_length = _PREFIX.unpack(content[: _PREFIX.size])
    start = _PREFIX.size
    header = json.loads(content[start:][:header_length])
    header["kdf"]["n"] = 2**20
    changed_header = json.dumps(header, sort_keys=True, separators=(",", ":")).encode(
        "ascii"
    )
    body_start = start + header_length
    source.write_bytes(
        _PREFIX.pack(magic, len(changed_header)) + changed_header + content[body_start:]
    )
    monkeypatch.setattr(
        "crm_api.infrastructure.backups.container.hashlib.scrypt",
        lambda *args, **kwargs: pytest.fail("KDF must not run"),
    )

    with pytest.raises(InvalidBackupFormatError):
        decrypt_payload(
            source_path=source,
            destination_path=tmp_path / "restored.tar",
            passphrase="senha sintetica forte",
        )


def test_version_one_header_matches_the_accepted_adr(tmp_path: Path) -> None:
    source = _encrypt(tmp_path)
    content = source.read_bytes()
    _, header_length = _PREFIX.unpack(content[: _PREFIX.size])
    start = _PREFIX.size
    header = json.loads(content[slice(start, start + header_length)])

    assert set(header) == {
        "format_version",
        "app_version",
        "schema_revision",
        "created_at",
        "payload_bytes",
        "frame_count",
        "frame_size",
        "cipher",
        "kdf",
        "salt",
        "nonce_prefix",
    }
    assert header["cipher"] == "AES-256-GCM"
    assert header["kdf"] == {
        "name": "scrypt",
        "n": 32768,
        "r": 8,
        "p": 1,
        "dklen": 32,
        "maxmem": 67108864,
    }
