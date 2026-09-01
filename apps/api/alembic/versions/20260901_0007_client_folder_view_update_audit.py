"""Extend the audit catalog with client folder view and update actions.

Revision ID: 20260901_0007
Revises: 20260830_0006
Create Date: 2026-09-01 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260901_0007"
down_revision: str | Sequence[str] | None = "20260830_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUDIT_ACTION_CONSTRAINT = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created', 'client_folder.viewed', 'client_folder.updated')"
)
_PREVIOUS_AUDIT_ACTION_CONSTRAINT = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created')"
)


def _replace_action_catalog(*, include_view_and_update: bool) -> None:
    """Mantém o check do catálogo de ações portável entre os dialetos."""
    action_constraint = (
        _AUDIT_ACTION_CONSTRAINT
        if include_view_and_update
        else _PREVIOUS_AUDIT_ACTION_CONSTRAINT
    )
    with op.batch_alter_table("audit_events", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_audit_events_action", type_="check")
        batch_op.create_check_constraint("ck_audit_events_action", action_constraint)


def upgrade() -> None:
    """Allow the client folder view/update audit actions."""
    _replace_action_catalog(include_view_and_update=True)


def downgrade() -> None:
    """Remove the new audit values before restoring the older catalog."""
    op.execute(
        sa.text(
            "DELETE FROM audit_events WHERE action IN "
            "('client_folder.viewed', 'client_folder.updated')"
        )
    )
    _replace_action_catalog(include_view_and_update=False)
