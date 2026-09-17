"""Add legacy import operation to the audit catalog.

Revision ID: 20260915_0013
Revises: 20260904_0012
Create Date: 2026-09-15 18:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0013"
down_revision: str | Sequence[str] | None = "20260904_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CURRENT_ACTIONS = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created', 'client_folder.viewed', 'client_folder.updated', "
    "'client_folder.profile_exported', 'document.stored', 'document.viewed', "
    "'document.exported', 'document.status_updated', 'message_template.created', "
    "'message_template.updated', 'message_template.deleted', "
    "'recipient_candidates.viewed')"
)
_NEXT_ACTIONS = _CURRENT_ACTIONS[:-1] + ", 'legacy_import.completed')"
_CURRENT_RESOURCES = (
    "resource_type IN ('owner_account', 'session', 'route', 'audit_log', "
    "'client_folder', 'document', 'message_template')"
)
_NEXT_RESOURCES = _CURRENT_RESOURCES[:-1] + ", 'legacy_import')"


def _replace_catalog(*, include_legacy_import: bool) -> None:
    with op.batch_alter_table("audit_events", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_audit_events_action", type_="check")
        batch_op.drop_constraint("ck_audit_events_resource_type", type_="check")
        batch_op.create_check_constraint(
            "ck_audit_events_action",
            _NEXT_ACTIONS if include_legacy_import else _CURRENT_ACTIONS,
        )
        batch_op.create_check_constraint(
            "ck_audit_events_resource_type",
            _NEXT_RESOURCES if include_legacy_import else _CURRENT_RESOURCES,
        )


def upgrade() -> None:
    _replace_catalog(include_legacy_import=True)


def downgrade() -> None:
    connection = op.get_bind()
    has_events = connection.scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM audit_events "
            "WHERE action = 'legacy_import.completed')"
        )
    )
    if has_events:
        raise RuntimeError(
            "cannot safely downgrade 20260915_0013 while legacy import audit "
            "events exist"
        )
    _replace_catalog(include_legacy_import=False)
