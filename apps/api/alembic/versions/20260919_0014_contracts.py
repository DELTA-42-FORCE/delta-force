"""Create contracts and exact installment schedules.

Revision ID: 20260919_0014
Revises: 20260915_0013
Create Date: 2026-09-19 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260919_0014"
down_revision: str | Sequence[str] | None = "20260915_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CURRENT_ACTIONS = (
    "action IN ('auth.owner_setup', 'auth.login', 'auth.owner_profile_view', "
    "'auth.logout', 'auth.access_denied', 'audit.log_view', "
    "'client_folder.created', 'client_folder.viewed', 'client_folder.updated', "
    "'client_folder.profile_exported', 'document.stored', 'document.viewed', "
    "'document.exported', 'document.status_updated', 'message_template.created', "
    "'message_template.updated', 'message_template.deleted', "
    "'recipient_candidates.viewed', 'legacy_import.completed')"
)
_NEXT_ACTIONS = _CURRENT_ACTIONS[:-1] + (
    ", 'contract.created', 'contract.viewed', 'contract.installment_paid', "
    "'contract.cancelled')"
)
_CURRENT_RESOURCES = (
    "resource_type IN ('owner_account', 'session', 'route', 'audit_log', "
    "'client_folder', 'document', 'message_template', 'legacy_import')"
)
_NEXT_RESOURCES = _CURRENT_RESOURCES[:-1] + ", 'contract')"


def _replace_audit_catalog(*, include_contracts: bool) -> None:
    with op.batch_alter_table("audit_events", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_audit_events_action", type_="check")
        batch_op.drop_constraint("ck_audit_events_resource_type", type_="check")
        batch_op.create_check_constraint(
            "ck_audit_events_action",
            _NEXT_ACTIONS if include_contracts else _CURRENT_ACTIONS,
        )
        batch_op.create_check_constraint(
            "ck_audit_events_resource_type",
            _NEXT_RESOURCES if include_contracts else _CURRENT_RESOURCES,
        )


def upgrade() -> None:
    op.create_table(
        "contracts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_folder_id", sa.Uuid(), nullable=False),
        sa.Column("total_amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("deposit_amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("balance_amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("installment_count", sa.Integer(), nullable=False),
        sa.Column("signal_paid_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
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
            "total_amount_cents > 200000",
            name="ck_contracts_total_exceeds_deposit",
        ),
        sa.CheckConstraint(
            "deposit_amount_cents = 200000", name="ck_contracts_fixed_deposit"
        ),
        sa.CheckConstraint(
            "balance_amount_cents = total_amount_cents - deposit_amount_cents",
            name="ck_contracts_balance_consistent",
        ),
        sa.CheckConstraint(
            "installment_count BETWEEN 1 AND 600",
            name="ck_contracts_installment_count",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'paid', 'cancelled')",
            name="ck_contracts_status",
        ),
        sa.CheckConstraint(
            "(status = 'cancelled' AND cancelled_at IS NOT NULL) OR "
            "(status <> 'cancelled' AND cancelled_at IS NULL)",
            name="ck_contracts_cancellation_consistent",
        ),
        sa.ForeignKeyConstraint(
            ["client_folder_id"], ["client_folders.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contracts_client_folder_id", "contracts", ["client_folder_id"])
    op.create_table(
        "contract_installments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("number >= 1", name="ck_contract_installments_number"),
        sa.CheckConstraint(
            "amount_cents >= 1", name="ck_contract_installments_amount_positive"
        ),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "contract_id", "number", name="uq_contract_installments_contract_number"
        ),
    )
    op.create_index(
        "ix_contract_installments_contract_id",
        "contract_installments",
        ["contract_id"],
    )
    _replace_audit_catalog(include_contracts=True)


def downgrade() -> None:
    connection = op.get_bind()
    has_financial_data = connection.scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM contracts) OR "
            "EXISTS(SELECT 1 FROM contract_installments)"
        )
    )
    has_financial_audit = connection.scalar(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM audit_events WHERE action LIKE 'contract.%')"
        )
    )
    if has_financial_data or has_financial_audit:
        raise RuntimeError(
            "cannot safely downgrade 20260919_0014 while contract data or audit "
            "events exist"
        )
    _replace_audit_catalog(include_contracts=False)
    op.drop_index(
        "ix_contract_installments_contract_id", table_name="contract_installments"
    )
    op.drop_table("contract_installments")
    op.drop_index("ix_contracts_client_folder_id", table_name="contracts")
    op.drop_table("contracts")
