import json
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def test_prepare_signed_sidecar_copies_and_signs_a_synthetic_onedir(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    runtime = source / "api-runtime"
    runtime.mkdir(parents=True)
    (source / "crm-api-poc.exe").write_bytes(b"synthetic executable")
    (runtime / "runtime.bin").write_bytes(b"synthetic runtime")
    destination = tmp_path / "destination"
    script = (
        Path(__file__).resolve().parents[2] / "scripts" / "prepare_signed_sidecar.py"
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source-onedir",
            str(source),
            "--destination",
            str(destination),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    result = json.loads(completed.stdout)
    assert result["file_count"] == 2
    assert result["signature_algorithm"] == "Ed25519-synthetic-spike-only"

    manifest = (destination / "manifest.json").read_bytes()
    signature = (destination / "manifest.sig").read_bytes()
    public_key = Ed25519PublicKey.from_public_bytes(
        bytes.fromhex(
            "d75a980182b10ab7d54bfed3c964073a" "0ee172f3daa62325af021a68f707511a"
        )
    )
    public_key.verify(signature, manifest)
    parsed_manifest = json.loads(manifest)
    assert [entry["path"] for entry in parsed_manifest["entries"]] == [
        "api-runtime/runtime.bin",
        "crm-api-poc.exe",
    ]
    assert (destination / "crm-api-poc.exe").read_bytes() == b"synthetic executable"
