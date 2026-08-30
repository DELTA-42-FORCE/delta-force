"""Add the portable owner-creation lock table.

Revision ID: 20260829_0005
Revises: 20260820_0004
Create Date: 2026-08-29 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0005"
down_revision: str | Sequence[str] | None = "20260820_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the single-row table that replaces the PostgreSQL advisory lock."""
    op.create_table(
        "owner_slot",
        sa.Column("id", sa.Integer(), primary_key=True),
    )


def downgrade() -> None:
    """Drop the owner-creation lock table."""
    op.drop_table("owner_slot")
