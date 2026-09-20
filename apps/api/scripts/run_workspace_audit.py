"""Executa auditorias obrigatórias sem depender da sintaxe do shell hospedeiro."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys

API_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = API_ROOT.parents[1]


@dataclass(frozen=True)
class AuditCommand:
    label: str
    command: tuple[str, ...]
    working_directory: Path
    required: bool = True


def _executable(name: str) -> str:
    executable = shutil.which(name)
    return executable if executable is not None else name


def _commands(scope: str) -> list[AuditCommand]:
    commands: list[AuditCommand] = []
    if scope in {"all", "api"}:
        commands.extend(
            [
                AuditCommand(
                    "Bandit (segurança do código Python)",
                    (sys.executable, "-m", "bandit", "-r", "src"),
                    API_ROOT,
                ),
                AuditCommand(
                    "pip-audit (vulnerabilidades Python)",
                    (sys.executable, "-m", "pip_audit"),
                    API_ROOT,
                ),
                AuditCommand(
                    "Atualizações Python disponíveis (informativo)",
                    (sys.executable, "-m", "pip", "list", "--outdated"),
                    API_ROOT,
                    required=False,
                ),
            ]
        )
    if scope in {"all", "web"}:
        commands.extend(
            [
                AuditCommand(
                    "npm audit (web)",
                    (_executable("npm"), "--prefix", "apps/web", "audit"),
                    REPOSITORY_ROOT,
                ),
                AuditCommand(
                    "Atualizações web disponíveis (informativo)",
                    (_executable("npm"), "--prefix", "apps/web", "outdated"),
                    REPOSITORY_ROOT,
                    required=False,
                ),
            ]
        )
    if scope in {"all", "desktop"}:
        commands.extend(
            [
                AuditCommand(
                    "npm audit (desktop)",
                    (_executable("npm"), "--prefix", "apps/desktop", "audit"),
                    REPOSITORY_ROOT,
                ),
                AuditCommand(
                    "cargo-audit (vulnerabilidades Rust)",
                    (
                        _executable("cargo"),
                        "audit",
                        "--file",
                        "apps/desktop/src-tauri/Cargo.lock",
                    ),
                    REPOSITORY_ROOT,
                ),
                AuditCommand(
                    "Atualizações desktop disponíveis (informativo)",
                    (_executable("npm"), "--prefix", "apps/desktop", "outdated"),
                    REPOSITORY_ROOT,
                    required=False,
                ),
            ]
        )
    return commands


def run(scope: str) -> int:
    failed: list[str] = []
    for audit in _commands(scope):
        print(f"\n==> {audit.label}", flush=True)
        try:
            result = subprocess.run(
                audit.command,
                cwd=audit.working_directory,
                check=False,
            )
        except OSError as error:
            print(f"Não foi possível executar: {error}", file=sys.stderr)
            if audit.required:
                failed.append(audit.label)
            continue
        if audit.required and result.returncode != 0:
            failed.append(audit.label)

    if failed:
        print(
            "\nAuditorias obrigatórias com falha: " + ", ".join(failed),
            file=sys.stderr,
        )
        return 1
    print("\nAuditorias obrigatórias concluídas sem vulnerabilidades conhecidas.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scope", choices=("all", "api", "web", "desktop"))
    return run(parser.parse_args().scope)


if __name__ == "__main__":
    raise SystemExit(main())
