"""Prepare a signed, synthetic sidecar tree for the architecture spike."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

EXECUTABLE_NAME = "crm-api-poc.exe"
RUNTIME_DIRECTORY = "api-runtime"
MANIFEST_NAME = "manifest.json"
SIGNATURE_NAME = "manifest.sig"

# RFC 8032 test vector seed. This is deliberately public, synthetic and
# forbidden for production signing, update trust or any real release.
SYNTHETIC_SPIKE_PRIVATE_SEED = bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
)
SYNTHETIC_SPIKE_PUBLIC_KEY = bytes.fromhex(
    "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
)


def _is_reparse_point(path: Path) -> bool:
    metadata = path.lstat()
    attributes = getattr(metadata, "st_file_attributes", 0)
    return path.is_symlink() or bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    )


def _validate_source_tree(source: Path) -> None:
    if _is_reparse_point(source):
        raise RuntimeError("source onedir root is a reparse point")
    if not source.is_dir():
        raise RuntimeError("source onedir root is not a directory")

    top_level = {path.name for path in source.iterdir()}
    if top_level != {EXECUTABLE_NAME, RUNTIME_DIRECTORY}:
        raise RuntimeError("source onedir has an unexpected top-level layout")
    if not (source / EXECUTABLE_NAME).is_file():
        raise RuntimeError("source executable is missing")
    if not (source / RUNTIME_DIRECTORY).is_dir():
        raise RuntimeError("source runtime directory is missing")

    for root, directories, files in os.walk(source, followlinks=False):
        root_path = Path(root)
        for name in [*directories, *files]:
            path = root_path / name
            if _is_reparse_point(path):
                raise RuntimeError("source onedir contains a reparse point")
            if not path.is_dir() and not path.is_file():
                raise RuntimeError("source onedir contains a special file")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_entries(destination: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(
        (candidate for candidate in destination.rglob("*") if candidate.is_file()),
        key=lambda candidate: candidate.relative_to(destination).as_posix(),
    ):
        relative = path.relative_to(destination).as_posix()
        if relative in {MANIFEST_NAME, SIGNATURE_NAME}:
            continue
        if _is_reparse_point(path):
            raise RuntimeError("destination contains a reparse point")
        entries.append(
            {
                "path": relative,
                "sha256": _sha256(path),
                "size": path.stat().st_size,
            }
        )
    return entries


def _write_new_file(path: Path, content: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def prepare(source: Path, destination: Path) -> dict[str, Any]:
    source = source.resolve(strict=True)
    destination = destination.resolve(strict=False)
    if destination.exists():
        raise RuntimeError("destination must not already exist")
    if destination == source or destination.is_relative_to(source):
        raise RuntimeError("destination overlaps the source onedir")

    _validate_source_tree(source)
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copy2(source / EXECUTABLE_NAME, destination / EXECUTABLE_NAME)
    shutil.copytree(
        source / RUNTIME_DIRECTORY,
        destination / RUNTIME_DIRECTORY,
        symlinks=True,
    )
    _validate_source_tree(destination)

    entries = _manifest_entries(destination)
    manifest_bytes = json.dumps(
        {"entries": entries, "schema": 1},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    signing_key = Ed25519PrivateKey.from_private_bytes(SYNTHETIC_SPIKE_PRIVATE_SEED)
    public_key = signing_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    if public_key != SYNTHETIC_SPIKE_PUBLIC_KEY:
        raise RuntimeError("synthetic signing fixture key mismatch")
    signature = signing_key.sign(manifest_bytes)
    public_key_object = signing_key.public_key()
    public_key_object.verify(signature, manifest_bytes)

    _write_new_file(destination / MANIFEST_NAME, manifest_bytes)
    _write_new_file(destination / SIGNATURE_NAME, signature)
    return {
        "file_count": len(entries),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "signature_algorithm": "Ed25519-synthetic-spike-only",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-onedir", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    options = parser.parse_args()
    result = prepare(options.source_onedir, options.destination)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
