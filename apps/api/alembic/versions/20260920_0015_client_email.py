"""Add the optional, validated client email used by communications.

Revision ID: 20260920_0015
Revises: 20260919_0014
Create Date: 2026-09-20 21:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_0015"
down_revision: str | Sequence[str] | None = "20260919_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("client_folders") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(length=320), nullable=True))
        batch_op.create_check_constraint(
            "ck_client_folders_email_not_blank",
            "email IS NULL OR length(trim(email)) > 0",
        )


def downgrade() -> None:
    connection = op.get_bind()
    has_email = connection.scalar(
        sa.text("SELECT EXISTS(SELECT 1 FROM client_folders WHERE email IS NOT NULL)")
    )
    if has_email:
        raise RuntimeError(
            "cannot safely downgrade 20260920_0015 while client emails exist"
        )
    with op.batch_alter_table("client_folders") as batch_op:
        batch_op.drop_constraint("ck_client_folders_email_not_blank", type_="check")
        batch_op.drop_column("email")
