"""Create private document metadata and its audit catalog entries.

Revision ID: 20260902_0008
Revises: 20260901_0007
Create Date: 2026-09-02 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260902_0008"
down_revision: str | Sequence[str] | None = "20260901_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUDIT_ACTION_CONSTRAINT = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created', 'client_folder.viewed', 'client_folder.updated', "
    "'document.stored')"
)
_PREVIOUS_AUDIT_ACTION_CONSTRAINT = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created', 'client_folder.viewed', 'client_folder.updated')"
)
_AUDIT_RESOURCE_CONSTRAINT = (
    "resource_type IN ('owner_account', 'session', 'route', 'audit_log', "
    "'client_folder', 'document')"
)
_PREVIOUS_AUDIT_RESOURCE_CONSTRAINT = (
    "resource_type IN ('owner_account', 'session', 'route', 'audit_log', "
    "'client_folder')"
)


def _replace_audit_catalogs(*, include_document: bool) -> None:
    """Mantém os checks do catálogo de auditoria portáveis entre os dialetos."""
    action_constraint = (
        _AUDIT_ACTION_CONSTRAINT
        if include_document
        else _PREVIOUS_AUDIT_ACTION_CONSTRAINT
    )
    resource_constraint = (
        _AUDIT_RESOURCE_CONSTRAINT
        if include_document
        else _PREVIOUS_AUDIT_RESOURCE_CONSTRAINT
    )
    with op.batch_alter_table("audit_events", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_audit_events_action", type_="check")
        batch_op.drop_constraint("ck_audit_events_resource_type", type_="check")
        batch_op.create_check_constraint("ck_audit_events_action", action_constraint)
        batch_op.create_check_constraint(
            "ck_audit_events_resource_type", resource_constraint
        )


def upgrade() -> None:
    """Store only document metadata; the binary stays in the private tree."""
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("client_folder_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("media_type", sa.String(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column(
            "stored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["client_folder_id"],
            ["client_folders.id"],
            name="fk_documents_client_folder_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "media_type IN ('application/pdf', 'image/jpeg')",
            name="ck_documents_media_type",
        ),
        sa.CheckConstraint("byte_size > 0", name="ck_documents_byte_size_positive"),
        sa.CheckConstraint(
            "length(checksum_sha256) = 64", name="ck_documents_checksum_length"
        ),
        sa.CheckConstraint(
            "length(trim(original_filename)) > 0",
            name="ck_documents_original_filename_not_blank",
        ),
        # Declarada na criação porque o SQLite não suporta ALTER de constraint.
        sa.UniqueConstraint("storage_key", name="uq_documents_storage_key"),
    )
    op.create_index("ix_documents_client_folder_id", "documents", ["client_folder_id"])
    _replace_audit_catalogs(include_document=True)


def downgrade() -> None:
    """Recusa rollback que descartaria documentos ou auditoria append-only."""
    bind = op.get_bind()
    has_documents = bind.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM documents)"))
    if has_documents:
        raise RuntimeError(
            "cannot downgrade 20260902_0008 while stored documents exist; the "
            "files in the private tree would lose their metadata"
        )
    has_incompatible_events = bind.scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM audit_events WHERE action = "
            "'document.stored' OR resource_type = 'document')"
        )
    )
    if has_incompatible_events:
        raise RuntimeError(
            "cannot safely downgrade 20260902_0008 while document audit events "
            "exist; preserve the audit history and keep this migration"
        )
    _replace_audit_catalogs(include_document=False)
    op.drop_index("ix_documents_client_folder_id", table_name="documents")
    op.drop_table("documents")
