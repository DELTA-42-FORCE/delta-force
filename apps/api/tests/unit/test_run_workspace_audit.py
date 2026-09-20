from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_workspace_audit.py"
SCRIPT_SPEC = spec_from_file_location("run_workspace_audit", SCRIPT_PATH)
assert SCRIPT_SPEC is not None and SCRIPT_SPEC.loader is not None
run_workspace_audit = module_from_spec(SCRIPT_SPEC)
sys.modules[SCRIPT_SPEC.name] = run_workspace_audit
SCRIPT_SPEC.loader.exec_module(run_workspace_audit)


def test_required_failure_does_not_skip_remaining_audits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []
    return_codes = iter((1, 0, 1))

    def fake_run(
        command: tuple[str, ...], *, cwd: Path, check: bool
    ) -> SimpleNamespace:
        del cwd, check
        calls.append(command)
        return SimpleNamespace(returncode=next(return_codes))

    monkeypatch.setattr(run_workspace_audit.subprocess, "run", fake_run)

    assert run_workspace_audit.run("api") == 1
    assert len(calls) == 3
    assert "bandit" in calls[0]
    assert "pip_audit" in calls[1]
    assert calls[2][-2:] == ("list", "--outdated")


def test_informational_failure_does_not_fail_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    return_codes = iter((0, 1))

    def fake_run(
        command: tuple[str, ...], *, cwd: Path, check: bool
    ) -> SimpleNamespace:
        del command, cwd, check
        return SimpleNamespace(returncode=next(return_codes))

    monkeypatch.setattr(run_workspace_audit.subprocess, "run", fake_run)

    assert run_workspace_audit.run("web") == 0
