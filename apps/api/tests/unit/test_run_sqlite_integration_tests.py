from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "run_sqlite_integration_tests.py"
)
SCRIPT_SPEC = spec_from_file_location("run_sqlite_integration_tests", SCRIPT_PATH)
assert SCRIPT_SPEC is not None and SCRIPT_SPEC.loader is not None
run_sqlite_integration_tests = module_from_spec(SCRIPT_SPEC)
SCRIPT_SPEC.loader.exec_module(run_sqlite_integration_tests)


def test_run_migrates_and_tests_a_disposable_temp_file(
    monkeypatch: "Any",
) -> None:
    calls: list[list[str]] = []
    database_urls: list[str] = []

    def fake_run(command: list[str], *, check: bool, env: dict[str, str]) -> None:
        del check
        calls.append(command)
        database_urls.append(env["DATABASE_URL"])

    monkeypatch.setattr(run_sqlite_integration_tests.subprocess, "run", fake_run)

    run_sqlite_integration_tests.run()

    assert [command[2] for command in calls] == ["alembic", "pytest"]
    assert calls[0][3:] == ["upgrade", "head"]
    assert calls[1][3:] == ["-m", "integration"]
    assert len(database_urls) == 2
    assert database_urls[0] == database_urls[1]
    database_url = database_urls[0]
    assert database_url.startswith("sqlite+aiosqlite:///")
    database_path = Path(database_url.removeprefix("sqlite+aiosqlite:///"))
    assert database_path.name.startswith("delta_force_integration_")
    assert database_path.suffix == ".sqlite3"
    assert not database_path.parent.exists()  # tempdir is cleaned up after run()
