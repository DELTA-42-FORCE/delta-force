"""Testes do contêiner criptográfico de backup DFCRMBK1."""

import json
from pathlib import Path
import struct

import pytest

from crm_api.infrastructure.backups import container
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


def test_container_round_trip_streams_multiple_frames(tmp_path: Path) -> None:
    content = b"abc" * 400_000
    source = _encrypt(tmp_path, content)
    restored = tmp_path / "restored.tar"

    header = read_backup_header(source)
    decrypt_payload(
        source_path=source,
        destination_path=restored,
        passphrase="senha sintetica forte",
    )

    assert header.frame_count == 2
    assert header.payload_bytes == len(content)
    assert header.schema_revision == "synthetic_revision"
    assert restored.read_bytes() == content
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
def test_invalid_physical_size_is_rejected_before_kdf(
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
    header = json.loads(content[slice(start, start + header_length)])
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


def test_invalid_frame_length_is_rejected_before_kdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _encrypt(tmp_path, b"payload spanning two frames" * 40_000)
    content = bytearray(source.read_bytes())
    _, header_length = _PREFIX.unpack(content[: _PREFIX.size])
    first_frame_length_offset = _PREFIX.size + header_length
    frame_length_slice = slice(first_frame_length_offset, first_frame_length_offset + 4)
    content[frame_length_slice] = struct.pack(">I", 1)
    source.write_bytes(content)
    monkeypatch.setattr(
        "crm_api.infrastructure.backups.container.hashlib.scrypt",
        lambda *args, **kwargs: pytest.fail("KDF must not run"),
    )

    with pytest.raises(InvalidBackupFormatError, match="frame length"):
        decrypt_payload(
            source_path=source,
            destination_path=tmp_path / "restored.tar",
            passphrase="senha sintetica forte",
        )


def test_header_matches_the_accepted_v1_format(tmp_path: Path) -> None:
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


def test_header_validation_uses_the_open_file_descriptor_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _encrypt(tmp_path)

    def reject_path_stat(_path: Path, *_args: object, **_kwargs: object) -> None:
        pytest.fail("validation must use the already-open file descriptor")

    monkeypatch.setattr(Path, "stat", reject_path_stat)

    header = read_backup_header(source)

    assert header.payload_bytes == len(b"conteudo sintetico")


def test_container_matches_the_dfcrmbk1_golden_vector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = tmp_path / "payload.tar"
    destination = tmp_path / "backup.dfcrmbak"
    payload.write_bytes(b"vector")
    monkeypatch.setattr(container.os, "urandom", lambda size: bytes(range(size)))

    encrypt_payload(
        payload_path=payload,
        destination_path=destination,
        passphrase="Vetor Sintetico 2026",
        app_version="0.1.0",
        created_at="2026-09-24T00:00:00Z",
        schema_revision="20260920_0016",
    )

    assert destination.read_bytes().hex() == (
        "444643524d424b31000001497b226170705f76657273696f6e223a22302e312e30222c"
        "22636970686572223a224145532d3235362d47434d222c22637265617465645f617422"
        "3a22323032362d30392d32345430303a30303a30305a222c22666f726d61745f766572"
        "73696f6e223a312c226672616d655f636f756e74223a312c226672616d655f73697a65"
        "223a313034383537362c226b6466223a7b22646b6c656e223a33322c226d61786d656d"
        "223a36373130383836342c226e223a33323736382c226e616d65223a22736372797074"
        "222c2270223a312c2272223a387d2c226e6f6e63655f707265666978223a2241414543"
        "417751464267633d222c227061796c6f61645f6279746573223a362c2273616c74223a"
        "2241414543417751464267634943516f4c4441304f44773d3d222c22736368656d615f"
        "7265766973696f6e223a2232303236303932305f30303136227d00000006d305ddea4c"
        "99c66a625833fb029f2dd2138bce3b5c69"
    )


def test_encryption_does_not_overwrite_an_existing_destination(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "payload.tar"
    destination = tmp_path / "backup.partial"
    payload.write_bytes(b"payload")
    destination.write_bytes(b"existing content")

    with pytest.raises(FileExistsError):
        encrypt_payload(
            payload_path=payload,
            destination_path=destination,
            passphrase="senha sintetica forte",
            app_version="0.1.0",
            created_at="2026-09-19T20:00:00Z",
            schema_revision="synthetic_revision",
        )

    assert destination.read_bytes() == b"existing content"
