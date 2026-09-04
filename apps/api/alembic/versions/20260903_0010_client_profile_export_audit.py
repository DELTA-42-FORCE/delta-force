"""Extend the audit catalog with the client profile export action.

Revision ID: 20260903_0010
Revises: 20260902_0009
Create Date: 2026-09-03 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_0010"
down_revision: str | Sequence[str] | None = "20260902_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUDIT_ACTION_CONSTRAINT = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created', 'client_folder.viewed', 'client_folder.updated', "
    "'client_folder.profile_exported', 'document.stored', 'document.viewed', "
    "'document.exported')"
)
_PREVIOUS_AUDIT_ACTION_CONSTRAINT = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created', 'client_folder.viewed', 'client_folder.updated', "
    "'document.stored', 'document.viewed', 'document.exported')"
)


def _replace_action_catalog(*, include_profile_export: bool) -> None:
    """Mantém o check do catálogo de ações portável entre os dialetos."""
    action_constraint = (
        _AUDIT_ACTION_CONSTRAINT
        if include_profile_export
        else _PREVIOUS_AUDIT_ACTION_CONSTRAINT
    )
    with op.batch_alter_table("audit_events", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_audit_events_action", type_="check")
        batch_op.create_check_constraint("ck_audit_events_action", action_constraint)


def upgrade() -> None:
    """Allow the client profile export audit action."""
    _replace_action_catalog(include_profile_export=True)


def downgrade() -> None:
    """Recusa rollback que descartaria eventos de auditoria append-only."""
    has_incompatible_events = op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM audit_events WHERE action = "
            "'client_folder.profile_exported')"
        )
    )
    if has_incompatible_events:
        raise RuntimeError(
            "cannot safely downgrade 20260903_0010 while client profile export "
            "audit events exist; preserve the audit history and keep this migration"
        )
    _replace_action_catalog(include_profile_export=False)
