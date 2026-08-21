"""Create a deterministic digest of the versionable spike source inputs."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath


ISSUE_PATH = PurePosixPath("spikes/issue-43-windows")
REPORT_PATH = ISSUE_PATH / "evidence/first-spike-report.md"


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def versionable_paths(root: Path) -> list[PurePosixPath]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            ISSUE_PATH.as_posix(),
        ],
        cwd=root,
        check=True,
        capture_output=True,
    )
    paths = {
        PurePosixPath(raw.decode("utf-8")) for raw in result.stdout.split(b"\0") if raw
    }
    paths.discard(REPORT_PATH)
    if not paths:
        raise RuntimeError("No versionable spike source inputs were found.")
    return sorted(paths, key=lambda path: path.as_posix().encode("utf-8"))


def source_digest(root: Path, paths: list[PurePosixPath]) -> str:
    manifest = bytearray()
    for path in paths:
        absolute_path = root.joinpath(*path.parts)
        if absolute_path.is_symlink() or not absolute_path.is_file():
            raise RuntimeError(f"Refusing non-regular source input: {path}")
        file_digest = hashlib.sha256(absolute_path.read_bytes()).hexdigest()
        manifest.extend(f"{file_digest}  {path.as_posix()}\n".encode("utf-8"))
    return hashlib.sha256(manifest).hexdigest()


def main() -> None:
    root = repository_root()
    paths = versionable_paths(root)
    print(
        json.dumps(
            {
                "algorithm": "sha256-of-sorted-sha256-path-lines-v1",
                "file_count": len(paths),
                "source_digest": source_digest(root, paths),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
