"""Add the is_admin flag to users.

Revision ID: 20260812_0003
Revises: 20260812_0002
Create Date: 2026-08-12 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0003"
down_revision: str | Sequence[str] | None = "20260812_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add ``is_admin`` so the administrator role can be distinguished."""
    op.add_column(
        "users",
        sa.Column(
            "is_admin", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    """Drop ``is_admin``."""
    op.drop_column("users", "is_admin")
