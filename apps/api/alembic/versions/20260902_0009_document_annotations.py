"""Add optional document annotations and view/export audit actions.

Revision ID: 20260902_0009
Revises: 20260902_0008
Create Date: 2026-09-02 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260902_0009"
down_revision: str | Sequence[str] | None = "20260902_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUDIT_ACTION_CONSTRAINT = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created', 'client_folder.viewed', 'client_folder.updated', "
    "'document.stored', 'document.viewed', 'document.exported')"
)
_PREVIOUS_AUDIT_ACTION_CONSTRAINT = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created', 'client_folder.viewed', 'client_folder.updated', "
    "'document.stored')"
)

_ANNOTATION_COLUMNS = ("title", "category", "notes")


def _replace_action_catalog(*, include_view_and_export: bool) -> None:
    """Mantém o check do catálogo de ações portável entre os dialetos."""
    action_constraint = (
        _AUDIT_ACTION_CONSTRAINT
        if include_view_and_export
        else _PREVIOUS_AUDIT_ACTION_CONSTRAINT
    )
    with op.batch_alter_table("audit_events", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_audit_events_action", type_="check")
        batch_op.create_check_constraint("ck_audit_events_action", action_constraint)


def upgrade() -> None:
    """Annotations stay optional: no document type is ever required."""
    with op.batch_alter_table("documents") as batch_op:
        for column_name in _ANNOTATION_COLUMNS:
            batch_op.add_column(sa.Column(column_name, sa.String(), nullable=True))
    _replace_action_catalog(include_view_and_export=True)


def downgrade() -> None:
    """Recusa rollback que descartaria auditoria append-only de documentos."""
    has_incompatible_events = op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM audit_events WHERE action IN "
            "('document.viewed', 'document.exported'))"
        )
    )
    if has_incompatible_events:
        raise RuntimeError(
            "cannot safely downgrade 20260902_0009 while document view/export "
            "audit events exist; preserve the audit history and keep this migration"
        )
    _replace_action_catalog(include_view_and_export=False)
    with op.batch_alter_table("documents") as batch_op:
        for column_name in _ANNOTATION_COLUMNS:
            batch_op.drop_column(column_name)
