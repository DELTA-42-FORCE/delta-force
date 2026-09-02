from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

API_DIRECTORY = Path(__file__).resolve().parents[2]


def test_alembic_has_a_single_migration_head() -> None:
    config = Config(str(API_DIRECTORY / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["20260902_0008"]
