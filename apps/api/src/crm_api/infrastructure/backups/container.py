"""Contêiner versionado de backup com AEAD por quadro.

O formato foi desenhado para que arquivos não confiáveis sejam limitados e
validados antes de executar o KDF. O conteúdo nunca é carregado inteiro em
memória e senha incorreta é indistinguível de corrupção criptográfica.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import unicodedata
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"DFCRMBK1"
FORMAT_VERSION = 1
HEADER_MAX_BYTES = 4096
FRAME_SIZE_BYTES = 1024 * 1024
MAX_PAYLOAD_BYTES = 2 * 1024**4
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MAX_MEMORY_BYTES = 64 * 1024 * 1024
SALT_BYTES = 16
NONCE_PREFIX_BYTES = 8
KEY_BYTES = 32
TAG_BYTES = 16

_PREFIX = struct.Struct(">8sI")
_FRAME_LENGTH = struct.Struct(">I")
_FRAME_AAD = struct.Struct(">IBI")
_HEADER_KEYS = frozenset(
    {
        "app_version",
        "cipher",
        "created_at",
        "format_version",
        "frame_count",
        "frame_size",
        "kdf",
        "nonce_prefix",
        "payload_size",
        "salt",
        "schema_revision",
        "scrypt_n",
        "scrypt_p",
        "scrypt_r",
    }
)


class BackupContainerError(Exception):
    """Base sanitizada para um contêiner que não pode ser processado."""


class InvalidBackupFormatError(BackupContainerError):
    pass


class BackupPasswordOrIntegrityError(BackupContainerError):
    pass


@dataclass(frozen=True, slots=True)
class BackupHeader:
    app_version: str
    created_at: str
    frame_count: int
    payload_size: int
    schema_revision: str
    salt: bytes
    nonce_prefix: bytes
    canonical_bytes: bytes


def encrypt_payload(
    *,
    payload_path: Path,
    destination_path: Path,
    passphrase: str,
    app_version: str,
    created_at: str,
    schema_revision: str,
) -> BackupHeader:
    """Cifra um payload existente e publica somente no caminho parcial informado."""
    payload_size = payload_path.stat().st_size
    if not 0 < payload_size <= MAX_PAYLOAD_BYTES:
        raise InvalidBackupFormatError("backup payload size is outside safe limits")
    frame_count = math.ceil(payload_size / FRAME_SIZE_BYTES)
    if frame_count > 2**32:
        raise InvalidBackupFormatError("backup payload requires too many frames")

    salt = os.urandom(SALT_BYTES)
    nonce_prefix = os.urandom(NONCE_PREFIX_BYTES)
    header_data = {
        "app_version": _bounded_ascii(app_version, field="app_version"),
        "cipher": "aes-256-gcm",
        "created_at": _bounded_ascii(created_at, field="created_at"),
        "format_version": FORMAT_VERSION,
        "frame_count": frame_count,
        "frame_size": FRAME_SIZE_BYTES,
        "kdf": "scrypt",
        "nonce_prefix": base64.b64encode(nonce_prefix).decode("ascii"),
        "payload_size": payload_size,
        "salt": base64.b64encode(salt).decode("ascii"),
        "schema_revision": _bounded_ascii(schema_revision, field="schema_revision"),
        "scrypt_n": SCRYPT_N,
        "scrypt_p": SCRYPT_P,
        "scrypt_r": SCRYPT_R,
    }
    header_bytes = _canonical_json(header_data)
    if len(header_bytes) > HEADER_MAX_BYTES:
        raise InvalidBackupFormatError("backup header is too large")
    header = _validated_header(header_data, header_bytes)
    key = _derive_key(passphrase=passphrase, salt=salt)
    cipher = AESGCM(key)
    header_digest = hashlib.sha256(header_bytes).digest()

    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    descriptor = os.open(destination_path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output, payload_path.open("rb") as payload:
            output.write(_PREFIX.pack(MAGIC, len(header_bytes)))
            output.write(header_bytes)
            remaining = payload_size
            for index in range(frame_count):
                expected = min(FRAME_SIZE_BYTES, remaining)
                plaintext = payload.read(expected)
                if len(plaintext) != expected:
                    raise InvalidBackupFormatError(
                        "backup payload changed while it was encrypted"
                    )
                remaining -= expected
                is_last = index == frame_count - 1
                nonce = nonce_prefix + index.to_bytes(4, "big")
                aad = header_digest + _FRAME_AAD.pack(index, is_last, expected)
                ciphertext = cipher.encrypt(nonce, plaintext, aad)
                output.write(_FRAME_LENGTH.pack(expected))
                output.write(ciphertext)
            if remaining != 0 or payload.read(1):
                raise InvalidBackupFormatError(
                    "backup payload changed while it was encrypted"
                )
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        destination_path.unlink(missing_ok=True)
        raise
    return header


def decrypt_payload(
    *, source_path: Path, destination_path: Path, passphrase: str
) -> BackupHeader:
    """Valida e decifra um contêiner sem publicar conteúdo parcial."""
    with source_path.open("rb") as source:
        header = _read_header_from(source, source_size=source_path.stat().st_size)
        key = _derive_key(passphrase=passphrase, salt=header.salt)
        cipher = AESGCM(key)
        header_digest = hashlib.sha256(header.canonical_bytes).digest()
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
        descriptor = os.open(destination_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as output:
                remaining = header.payload_size
                for index in range(header.frame_count):
                    encoded_length = source.read(_FRAME_LENGTH.size)
                    if len(encoded_length) != _FRAME_LENGTH.size:
                        raise InvalidBackupFormatError("backup frame is truncated")
                    (plaintext_length,) = _FRAME_LENGTH.unpack(encoded_length)
                    expected = min(FRAME_SIZE_BYTES, remaining)
                    if plaintext_length != expected:
                        raise InvalidBackupFormatError("backup frame length is invalid")
                    ciphertext = source.read(plaintext_length + TAG_BYTES)
                    if len(ciphertext) != plaintext_length + TAG_BYTES:
                        raise InvalidBackupFormatError("backup frame is truncated")
                    is_last = index == header.frame_count - 1
                    nonce = header.nonce_prefix + index.to_bytes(4, "big")
                    aad = header_digest + _FRAME_AAD.pack(
                        index, is_last, plaintext_length
                    )
                    try:
                        plaintext = cipher.decrypt(nonce, ciphertext, aad)
                    except InvalidTag:
                        raise BackupPasswordOrIntegrityError(
                            "backup password is wrong or content is corrupted"
                        ) from None
                    output.write(plaintext)
                    remaining -= plaintext_length
                if remaining != 0 or source.read(1):
                    raise InvalidBackupFormatError(
                        "backup contains missing or extra frames"
                    )
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            destination_path.unlink(missing_ok=True)
            raise
    return header


def read_backup_header(source_path: Path) -> BackupHeader:
    """Lê somente metadados públicos com todos os limites pré-KDF."""
    with source_path.open("rb") as source:
        return _read_header_from(source, source_size=source_path.stat().st_size)


def _read_header_from(source: BinaryIO, *, source_size: int) -> BackupHeader:
    prefix = source.read(_PREFIX.size)
    if len(prefix) != _PREFIX.size:
        raise InvalidBackupFormatError("backup header is truncated")
    magic, header_length = _PREFIX.unpack(prefix)
    if magic != MAGIC or not 1 <= header_length <= HEADER_MAX_BYTES:
        raise InvalidBackupFormatError("backup header is invalid")
    header_bytes = source.read(header_length)
    if len(header_bytes) != header_length:
        raise InvalidBackupFormatError("backup header is truncated")
    try:
        header_data = json.loads(header_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise InvalidBackupFormatError("backup header is invalid") from None
    if _canonical_json(header_data) != header_bytes:
        raise InvalidBackupFormatError("backup header is not canonical")
    header = _validated_header(header_data, header_bytes)
    expected_size = _PREFIX.size + header_length
    remaining = header.payload_size
    for _ in range(header.frame_count):
        plaintext_length = min(FRAME_SIZE_BYTES, remaining)
        expected_size += _FRAME_LENGTH.size + plaintext_length + TAG_BYTES
        remaining -= plaintext_length
    if remaining != 0 or expected_size != source_size:
        raise InvalidBackupFormatError("backup size does not match its header")
    return header


def _validated_header(data: object, canonical_bytes: bytes) -> BackupHeader:
    if not isinstance(data, dict) or set(data) != _HEADER_KEYS:
        raise InvalidBackupFormatError("backup header fields are invalid")
    exact_values = {
        "format_version": FORMAT_VERSION,
        "cipher": "aes-256-gcm",
        "kdf": "scrypt",
        "frame_size": FRAME_SIZE_BYTES,
        "scrypt_n": SCRYPT_N,
        "scrypt_r": SCRYPT_R,
        "scrypt_p": SCRYPT_P,
    }
    for key in ("format_version", "frame_size", "scrypt_n", "scrypt_r", "scrypt_p"):
        if type(data.get(key)) is not int:
            raise InvalidBackupFormatError(
                "backup algorithms or limits are unsupported"
            )
    if any(data.get(key) != value for key, value in exact_values.items()):
        raise InvalidBackupFormatError("backup algorithms or limits are unsupported")
    payload_size = _strict_integer(data.get("payload_size"), "payload_size")
    frame_count = _strict_integer(data.get("frame_count"), "frame_count")
    if not 0 < payload_size <= MAX_PAYLOAD_BYTES:
        raise InvalidBackupFormatError("backup payload size is outside safe limits")
    expected_frames = math.ceil(payload_size / FRAME_SIZE_BYTES)
    if frame_count != expected_frames or frame_count > 2**32:
        raise InvalidBackupFormatError("backup frame count is invalid")
    salt = _decode_fixed_base64(data.get("salt"), SALT_BYTES, "salt")
    nonce_prefix = _decode_fixed_base64(
        data.get("nonce_prefix"), NONCE_PREFIX_BYTES, "nonce_prefix"
    )
    return BackupHeader(
        app_version=_bounded_ascii(data.get("app_version"), field="app_version"),
        created_at=_bounded_ascii(data.get("created_at"), field="created_at"),
        frame_count=frame_count,
        payload_size=payload_size,
        schema_revision=_bounded_ascii(
            data.get("schema_revision"), field="schema_revision"
        ),
        salt=salt,
        nonce_prefix=nonce_prefix,
        canonical_bytes=canonical_bytes,
    )


def _derive_key(*, passphrase: str, salt: bytes) -> bytes:
    if not isinstance(passphrase, str):
        raise ValueError("backup passphrase must be text")
    normalized = unicodedata.normalize("NFC", passphrase)
    encoded = normalized.encode("utf-8")
    if not 12 <= len(encoded) <= 1024:
        raise ValueError("backup passphrase must contain between 12 and 1024 bytes")
    return hashlib.scrypt(
        encoded,
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=SCRYPT_MAX_MEMORY_BYTES,
        dklen=KEY_BYTES,
    )


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError):
        raise InvalidBackupFormatError("backup header is invalid") from None


def _strict_integer(value: object, field: str) -> int:
    if type(value) is not int:
        raise InvalidBackupFormatError(f"backup {field} is invalid")
    return value


def _bounded_ascii(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 128
        or not value.isascii()
    ):
        raise InvalidBackupFormatError(f"backup {field} is invalid")
    return value


def _decode_fixed_base64(value: object, length: int, field: str) -> bytes:
    if not isinstance(value, str) or len(value) > 128 or not value.isascii():
        raise InvalidBackupFormatError(f"backup {field} is invalid")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error):
        raise InvalidBackupFormatError(f"backup {field} is invalid") from None
    if len(decoded) != length:
        raise InvalidBackupFormatError(f"backup {field} is invalid")
    return decoded
