from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

import pytest

from crm_api.core.database_url_safety import ensure_loopback_database_url

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "run_integration_tests.py"
)
SCRIPT_SPEC = spec_from_file_location("run_integration_tests", SCRIPT_PATH)
assert SCRIPT_SPEC is not None and SCRIPT_SPEC.loader is not None
run_integration_tests = module_from_spec(SCRIPT_SPEC)
SCRIPT_SPEC.loader.exec_module(run_integration_tests)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://crm:crm@localhost:5432/crm",
        "postgresql+psycopg://crm:crm@127.0.0.1:5432/crm",
        "postgresql+psycopg://crm:crm@[::1]:5432/crm",
        "sqlite+aiosqlite:///./crm.sqlite3",
        "sqlite+aiosqlite:///:memory:",
    ],
)
def test_loopback_database_url_is_allowed(database_url: str) -> None:
    ensure_loopback_database_url(database_url)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://crm:crm@database.internal:5432/crm",
        "postgresql+psycopg://crm:crm@192.0.2.10:5432/crm",
    ],
)
def test_non_loopback_database_url_is_rejected(database_url: str) -> None:
    with pytest.raises(RuntimeError, match="non-loopback"):
        ensure_loopback_database_url(database_url)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://crm:crm@localhost:5432/crm?host=database.internal",
        "postgresql+psycopg://crm:crm@localhost:5432/crm?hostaddr=192.0.2.10",
        "postgresql+psycopg://crm:crm@localhost:5432/crm?service=remote",
        "postgresql+psycopg://crm:crm@localhost:5432/crm?%68ost=database.internal",
        "postgresql+psycopg://crm:crm@localhost:5432/crm?dbname=production",
    ],
)
def test_database_destination_override_is_rejected(database_url: str) -> None:
    with pytest.raises(RuntimeError, match="destination override"):
        ensure_loopback_database_url(database_url)


def test_run_rejects_remote_database_before_connecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        database_url=("postgresql+psycopg://crm:crm@database.internal:5432/crm")
    )
    monkeypatch.setattr(run_integration_tests, "get_settings", lambda: settings)

    def fail_if_database_is_contacted(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("remote database must not be contacted")

    monkeypatch.setattr(
        run_integration_tests.psycopg, "connect", fail_if_database_is_contacted
    )

    with pytest.raises(RuntimeError, match="non-loopback"):
        run_integration_tests.run()
