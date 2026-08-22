"""Create the append-only audit event table.

Revision ID: 20260820_0004
Revises: 20260819_0003
Create Date: 2026-08-20 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0004"
down_revision: str | Sequence[str] | None = "20260819_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the portable audit log foundation."""
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("actor_kind", sa.String(), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "actor_kind IN ('authenticated', 'anonymous')",
            name="ck_audit_events_actor_kind",
        ),
        sa.CheckConstraint(
            "result IN ('success', 'denied', 'failure')",
            name="ck_audit_events_result",
        ),
        sa.CheckConstraint(
            "action IN ('auth.owner_setup', 'auth.login', "
            "'auth.owner_profile_view', 'auth.logout', "
            "'auth.access_denied', 'audit.log_view')",
            name="ck_audit_events_action",
        ),
        sa.CheckConstraint(
            "resource_type IN ('owner_account', 'session', 'route', " "'audit_log')",
            name="ck_audit_events_resource_type",
        ),
        sa.CheckConstraint(
            "(actor_kind = 'authenticated' AND actor_user_id IS NOT NULL) OR "
            "(actor_kind = 'anonymous' AND actor_user_id IS NULL)",
            name="ck_audit_events_actor_identity",
        ),
    )
    op.create_index(
        "ix_audit_events_actor_user_id",
        "audit_events",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_audit_events_occurred_at_id",
        "audit_events",
        ["occurred_at", "id"],
    )


def downgrade() -> None:
    """Drop only the audit log foundation."""
    op.drop_index("ix_audit_events_occurred_at_id", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_table("audit_events")
