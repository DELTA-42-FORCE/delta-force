"""Disposable runtime proof for the Windows architecture decision."""

from spike_runtime.app import create_app
from spike_runtime.security import RuntimeGate
from spike_runtime.sqlite_smoke import run_sqlite_smoke

__all__ = ["RuntimeGate", "create_app", "run_sqlite_smoke"]
