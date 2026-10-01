"""Add the sanitized backup audit catalog.

Revision ID: 20260930_0017
Revises: 20260920_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260930_0017"
down_revision: str | Sequence[str] | None = "20260920_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_ACTIONS = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created', 'client_folder.viewed', 'client_folder.updated', "
    "'client_folder.profile_exported', 'document.stored', 'document.viewed', "
    "'document.exported', 'document.status_updated', 'message_template.created', "
    "'message_template.updated', 'message_template.deleted', "
    "'recipient_candidates.viewed', 'legacy_import.completed', "
    "'contract.created', 'contract.viewed', 'contract.installment_paid', "
    "'contract.cancelled', 'email_sender_settings.updated', "
    "'email_sender_settings.viewed', 'email_dispatch.batch_started', "
    "'email_dispatch.batch_completed', 'email_dispatch.batch_failed', "
    "'email_dispatch.history_viewed')"
)
_NEW_ACTIONS = _OLD_ACTIONS[:-1] + (
    ", 'backup.created', 'backup.restore_reviewed', 'backup.restore_authorized', "
    "'backup.restore_applied', 'backup.reminder_updated')"
)
_OLD_RESOURCES = (
    "resource_type IN ('owner_account', 'session', 'route', 'audit_log', "
    "'client_folder', 'document', 'message_template', 'legacy_import', "
    "'contract', 'email_sender_settings', 'email_dispatch')"
)


def _replace_catalog(*, backup: bool) -> None:
    with op.batch_alter_table("audit_events", recreate="always") as batch:
        batch.drop_constraint("ck_audit_events_action", type_="check")
        batch.drop_constraint("ck_audit_events_resource_type", type_="check")
        batch.create_check_constraint(
            "ck_audit_events_action", _NEW_ACTIONS if backup else _OLD_ACTIONS
        )
        batch.create_check_constraint(
            "ck_audit_events_resource_type",
            _OLD_RESOURCES[:-1] + ", 'backup')" if backup else _OLD_RESOURCES,
        )


def upgrade() -> None:
    _replace_catalog(backup=True)


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM audit_events WHERE resource_type = 'backup')"
        )
    ):
        raise RuntimeError("backup audit data must be preserved before downgrade")
    _replace_catalog(backup=False)
