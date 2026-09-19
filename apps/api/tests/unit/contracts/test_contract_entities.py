"""Provas das regras financeiras exatas de #29."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from crm_api.domain.contracts.entities import (
    FIXED_DEPOSIT_CENTS,
    Contract,
    ContractInstallment,
    ContractStatus,
    build_installment_plan,
)


def test_plan_distributes_residual_cents_to_first_installments() -> None:
    plan = build_installment_plan(
        total_amount_cents=1_200_003,
        installment_count=3,
        signal_paid_on=date(2026, 3, 10),
    )

    assert [item.amount_cents for item in plan] == [333_335, 333_334, 333_334]
    assert sum(item.amount_cents for item in plan) + FIXED_DEPOSIT_CENTS == 1_200_003
    assert [item.due_date for item in plan] == [
        date(2026, 4, 10),
        date(2026, 5, 10),
        date(2026, 6, 10),
    ]


def test_missing_anchor_day_moves_only_that_occurrence_to_next_month() -> None:
    plan = build_installment_plan(
        total_amount_cents=500_000,
        installment_count=3,
        signal_paid_on=date(2026, 1, 31),
    )

    assert [item.due_date for item in plan] == [
        date(2026, 3, 1),
        date(2026, 3, 31),
        date(2026, 5, 1),
    ]


def test_plan_rejects_total_that_does_not_leave_one_cent_per_installment() -> None:
    with pytest.raises(ValueError, match="at least one cent"):
        build_installment_plan(
            total_amount_cents=200_001,
            installment_count=2,
            signal_paid_on=date(2026, 1, 1),
        )


def test_overdue_is_derived_only_for_active_unpaid_installments() -> None:
    now = datetime(2026, 4, 1, tzinfo=UTC)
    installment = ContractInstallment(
        id=uuid4(),
        number=1,
        amount_cents=100_000,
        due_date=date(2026, 3, 31),
        paid_on=None,
    )
    contract = Contract(
        id=uuid4(),
        client_folder_id=uuid4(),
        total_amount_cents=300_000,
        deposit_amount_cents=FIXED_DEPOSIT_CENTS,
        balance_amount_cents=100_000,
        installment_count=1,
        signal_paid_on=date(2026, 2, 28),
        status=ContractStatus.ACTIVE,
        cancelled_at=None,
        installments=(installment,),
        created_at=now,
        updated_at=now,
    )

    assert contract.is_overdue(as_of=date(2026, 4, 1)) is True
    assert contract.is_overdue(as_of=date(2026, 3, 31)) is False


def test_paid_contract_requires_every_installment_to_be_paid() -> None:
    now = datetime(2026, 4, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="paid contract"):
        Contract(
            id=uuid4(),
            client_folder_id=uuid4(),
            total_amount_cents=300_000,
            deposit_amount_cents=FIXED_DEPOSIT_CENTS,
            balance_amount_cents=100_000,
            installment_count=1,
            signal_paid_on=date(2026, 2, 28),
            status=ContractStatus.PAID,
            cancelled_at=None,
            installments=(
                ContractInstallment(
                    id=uuid4(),
                    number=1,
                    amount_cents=100_000,
                    due_date=date(2026, 3, 28),
                    paid_on=None,
                ),
            ),
            created_at=now,
            updated_at=now,
        )
