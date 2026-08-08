"""Establish the initial migration baseline.

Revision ID: 20260808_0001
Revises:
Create Date: 2026-08-08 00:00:00
"""

from collections.abc import Sequence

revision: str = "20260808_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the Alembic baseline before domain tables are introduced."""


def downgrade() -> None:
    """Return to a database with no application migrations."""
