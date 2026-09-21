"""Add secure sender settings and tracked email deliveries.

Revision ID: 20260920_0016
Revises: 20260920_0015
Create Date: 2026-09-20 21:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_0016"
down_revision: str | Sequence[str] | None = "20260920_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CURRENT_ACTIONS = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created', 'client_folder.viewed', 'client_folder.updated', "
    "'client_folder.profile_exported', 'document.stored', 'document.viewed', "
    "'document.exported', 'document.status_updated', 'message_template.created', "
    "'message_template.updated', 'message_template.deleted', "
    "'recipient_candidates.viewed', 'legacy_import.completed', "
    "'contract.created', 'contract.viewed', 'contract.installment_paid', "
    "'contract.cancelled')"
)
_NEXT_ACTIONS = _CURRENT_ACTIONS[:-1] + (
    ", 'email_sender_settings.updated', 'email_sender_settings.viewed', "
    "'email_dispatch.batch_started', 'email_dispatch.batch_completed', "
    "'email_dispatch.batch_failed', 'email_dispatch.history_viewed')"
)
_CURRENT_RESOURCES = (
    "resource_type IN ('owner_account', 'session', 'route', 'audit_log', "
    "'client_folder', 'document', 'message_template', 'legacy_import', 'contract')"
)
_NEXT_RESOURCES = _CURRENT_RESOURCES[:-1] + (
    ", 'email_sender_settings', 'email_dispatch')"
)


def _replace_audit_catalog(*, include_email: bool) -> None:
    with op.batch_alter_table("audit_events", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_audit_events_action", type_="check")
        batch_op.drop_constraint("ck_audit_events_resource_type", type_="check")
        batch_op.create_check_constraint(
            "ck_audit_events_action",
            _NEXT_ACTIONS if include_email else _CURRENT_ACTIONS,
        )
        batch_op.create_check_constraint(
            "ck_audit_events_resource_type",
            _NEXT_RESOURCES if include_email else _CURRENT_RESOURCES,
        )


def upgrade() -> None:
    op.create_table(
        "email_sender_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sender_name", sa.String(length=120), nullable=False),
        sa.Column("sender_email", sa.String(length=320), nullable=False),
        sa.Column("smtp_host", sa.String(length=253), nullable=False),
        sa.Column("smtp_port", sa.Integer(), nullable=False),
        sa.Column("security", sa.String(length=16), nullable=False),
        sa.Column("username", sa.String(length=320), nullable=True),
        sa.Column("max_recipients", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_email_sender_settings_singleton"),
        sa.CheckConstraint(
            "security IN ('starttls', 'tls', 'none_dev')",
            name="ck_email_sender_settings_security",
        ),
        sa.CheckConstraint(
            "smtp_port BETWEEN 1 AND 65535",
            name="ck_email_sender_settings_port",
        ),
        sa.CheckConstraint(
            "max_recipients BETWEEN 1 AND 100",
            name="ck_email_sender_settings_max_recipients",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "email_dispatches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=True),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("message_id", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("detail", sa.String(length=200), nullable=True),
        sa.Column("retry_of", sa.Uuid(), nullable=True),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'rejected', 'unknown', "
            "'skipped_duplicate', 'missing_email')",
            name="ck_email_dispatches_status",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"], ["client_folders.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["retry_of"], ["email_dispatches.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id"),
    )
    op.create_index(
        "ix_email_dispatches_attempted_at",
        "email_dispatches",
        ["attempted_at", "id"],
    )
    op.create_index(
        "ix_email_dispatches_template_client_status",
        "email_dispatches",
        ["template_id", "client_id", "status"],
    )
    op.create_index(
        "ix_email_dispatches_retry_of",
        "email_dispatches",
        ["retry_of"],
    )
    _replace_audit_catalog(include_email=True)


def downgrade() -> None:
    connection = op.get_bind()
    has_data = connection.scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM email_sender_settings) OR "
            "EXISTS(SELECT 1 FROM email_dispatches) OR "
            "EXISTS(SELECT 1 FROM audit_events WHERE action IN "
            "('email_sender_settings.updated', 'email_sender_settings.viewed', "
            "'email_dispatch.batch_started', 'email_dispatch.batch_completed', "
            "'email_dispatch.batch_failed', 'email_dispatch.history_viewed'))"
        )
    )
    if has_data:
        raise RuntimeError(
            "cannot safely downgrade 20260920_0016 while email data exists"
        )
    _replace_audit_catalog(include_email=False)
    op.drop_index("ix_email_dispatches_retry_of", table_name="email_dispatches")
    op.drop_index(
        "ix_email_dispatches_template_client_status",
        table_name="email_dispatches",
    )
    op.drop_index("ix_email_dispatches_attempted_at", table_name="email_dispatches")
    op.drop_table("email_dispatches")
    op.drop_table("email_sender_settings")
