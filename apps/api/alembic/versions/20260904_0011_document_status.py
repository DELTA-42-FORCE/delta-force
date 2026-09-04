"""Add document tracking status and its audit action.

Revision ID: 20260904_0011
Revises: 20260903_0010
Create Date: 2026-09-04 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_0011"
down_revision: str | Sequence[str] | None = "20260903_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUDIT_ACTION_CONSTRAINT = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created', 'client_folder.viewed', 'client_folder.updated', "
    "'client_folder.profile_exported', 'document.stored', 'document.viewed', "
    "'document.exported', 'document.status_updated')"
)
_PREVIOUS_AUDIT_ACTION_CONSTRAINT = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created', 'client_folder.viewed', 'client_folder.updated', "
    "'client_folder.profile_exported', 'document.stored', 'document.viewed', "
    "'document.exported')"
)
_DOCUMENT_STATUS_CONSTRAINT = (
    "status IN ('pending', 'received_regular', 'incorrect_incomplete')"
)


def _replace_action_catalog(*, include_status_update: bool) -> None:
    action_constraint = (
        _AUDIT_ACTION_CONSTRAINT
        if include_status_update
        else _PREVIOUS_AUDIT_ACTION_CONSTRAINT
    )
    with op.batch_alter_table("audit_events", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_audit_events_action", type_="check")
        batch_op.create_check_constraint("ck_audit_events_action", action_constraint)


def upgrade() -> None:
    """Existing and new documents start pending until the owner reviews them."""
    with op.batch_alter_table("documents", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(),
                nullable=False,
                server_default=sa.text("'pending'"),
            )
        )
        batch_op.create_check_constraint(
            "ck_documents_status", _DOCUMENT_STATUS_CONSTRAINT
        )
        batch_op.create_index("ix_documents_status", ["status"], unique=False)
    _replace_action_catalog(include_status_update=True)


def downgrade() -> None:
    """Never discard append-only status history during a rollback."""
    connection = op.get_bind()
    has_incompatible_events = connection.scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM audit_events WHERE action = "
            "'document.status_updated')"
        )
    )
    has_non_default_status = connection.scalar(
        sa.text("SELECT EXISTS(SELECT 1 FROM documents WHERE status != 'pending')")
    )
    if has_incompatible_events or has_non_default_status:
        raise RuntimeError(
            "cannot safely downgrade 20260904_0011 while document status data or "
            "audit events exist; preserve them and keep this migration"
        )
    _replace_action_catalog(include_status_update=False)
    with op.batch_alter_table("documents", recreate="always") as batch_op:
        batch_op.drop_index("ix_documents_status")
        batch_op.drop_constraint("ck_documents_status", type_="check")
        batch_op.drop_column("status")
