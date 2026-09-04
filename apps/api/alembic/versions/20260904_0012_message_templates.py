"""Create message templates and extend the audit catalog.

Revision ID: 20260904_0012
Revises: 20260904_0011
Create Date: 2026-09-04 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_0012"
down_revision: str | Sequence[str] | None = "20260904_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUDIT_ACTION_CONSTRAINT = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created', 'client_folder.viewed', 'client_folder.updated', "
    "'client_folder.profile_exported', 'document.stored', 'document.viewed', "
    "'document.exported', 'document.status_updated', 'message_template.created', "
    "'message_template.updated', 'message_template.deleted')"
)
_PREVIOUS_AUDIT_ACTION_CONSTRAINT = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created', 'client_folder.viewed', 'client_folder.updated', "
    "'client_folder.profile_exported', 'document.stored', 'document.viewed', "
    "'document.exported', 'document.status_updated')"
)
_AUDIT_RESOURCE_CONSTRAINT = (
    "resource_type IN ('owner_account', 'session', 'route', 'audit_log', "
    "'client_folder', 'document', 'message_template')"
)
_PREVIOUS_AUDIT_RESOURCE_CONSTRAINT = (
    "resource_type IN ('owner_account', 'session', 'route', 'audit_log', "
    "'client_folder', 'document')"
)


def _replace_audit_catalog(*, include_templates: bool) -> None:
    with op.batch_alter_table("audit_events", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_audit_events_action", type_="check")
        batch_op.drop_constraint("ck_audit_events_resource_type", type_="check")
        batch_op.create_check_constraint(
            "ck_audit_events_action",
            (
                _AUDIT_ACTION_CONSTRAINT
                if include_templates
                else _PREVIOUS_AUDIT_ACTION_CONSTRAINT
            ),
        )
        batch_op.create_check_constraint(
            "ck_audit_events_resource_type",
            (
                _AUDIT_RESOURCE_CONSTRAINT
                if include_templates
                else _PREVIOUS_AUDIT_RESOURCE_CONSTRAINT
            ),
        )


def upgrade() -> None:
    op.create_table(
        "message_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(name)) BETWEEN 1 AND 120",
            name="ck_message_templates_name_length",
        ),
        sa.CheckConstraint(
            "length(trim(subject)) BETWEEN 1 AND 200",
            name="ck_message_templates_subject_length",
        ),
        sa.CheckConstraint(
            "length(trim(body)) BETWEEN 1 AND 20000",
            name="ck_message_templates_body_length",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    _replace_audit_catalog(include_templates=True)


def downgrade() -> None:
    connection = op.get_bind()
    has_templates = connection.scalar(
        sa.text("SELECT EXISTS(SELECT 1 FROM message_templates)")
    )
    has_template_events = connection.scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM audit_events WHERE action LIKE "
            "'message_template.%')"
        )
    )
    if has_templates or has_template_events:
        raise RuntimeError(
            "cannot safely downgrade 20260904_0012 while message templates or "
            "their audit events exist"
        )
    _replace_audit_catalog(include_templates=False)
    op.drop_table("message_templates")
