"""Create flexible client folders and audit catalog entries.

Revision ID: 20260830_0006
Revises: 20260829_0005
Create Date: 2026-08-30 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0006"
down_revision: str | Sequence[str] | None = "20260829_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUDIT_ACTION_CONSTRAINT = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created')"
)
_LEGACY_AUDIT_ACTION_CONSTRAINT = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view')"
)
_AUDIT_RESOURCE_CONSTRAINT = (
    "resource_type IN ('owner_account', 'session', 'route', 'audit_log', "
    "'client_folder')"
)
_LEGACY_AUDIT_RESOURCE_CONSTRAINT = (
    "resource_type IN ('owner_account', 'session', 'route', 'audit_log')"
)


def _replace_audit_catalogs(*, include_client_folder: bool) -> None:
    """Mantém os checks do catálogo de auditoria portáveis entre os dialetos."""
    action_constraint = (
        _AUDIT_ACTION_CONSTRAINT
        if include_client_folder
        else _LEGACY_AUDIT_ACTION_CONSTRAINT
    )
    resource_constraint = (
        _AUDIT_RESOURCE_CONSTRAINT
        if include_client_folder
        else _LEGACY_AUDIT_RESOURCE_CONSTRAINT
    )
    with op.batch_alter_table("audit_events", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_audit_events_action", type_="check")
        batch_op.drop_constraint("ck_audit_events_resource_type", type_="check")
        batch_op.create_check_constraint("ck_audit_events_action", action_constraint)
        batch_op.create_check_constraint(
            "ck_audit_events_resource_type", resource_constraint
        )


def upgrade() -> None:
    """Create folders whose only required field is the identifying name."""
    op.create_table(
        "client_folders",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column(
            "profile_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "length(trim(display_name)) > 0",
            name="ck_client_folders_display_name_not_blank",
        ),
    )
    op.create_index(
        "ix_client_folders_display_name", "client_folders", ["display_name"]
    )
    _replace_audit_catalogs(include_client_folder=True)


def downgrade() -> None:
    """Remove folders and their audit values before restoring the older catalog."""
    op.execute(
        sa.text("DELETE FROM audit_events WHERE action = 'client_folder.created'")
    )
    _replace_audit_catalogs(include_client_folder=False)
    op.drop_index("ix_client_folders_display_name", table_name="client_folders")
    op.drop_table("client_folders")
