"""Entidades e regras exatas do parcelamento de contratos (#29)."""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

FIXED_DEPOSIT_CENTS = 200_000
MAX_INSTALLMENTS = 600


class ContractStatus(StrEnum):
    ACTIVE = "active"
    PAID = "paid"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class InstallmentPlanItem:
    number: int
    amount_cents: int
    due_date: date


@dataclass(frozen=True, slots=True)
class ContractInstallment:
    id: UUID
    number: int
    amount_cents: int
    due_date: date
    paid_on: date | None

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise ValueError("installment id must be a UUID")
        if self.number < 1:
            raise ValueError("installment number must be positive")
        if self.amount_cents < 1:
            raise ValueError("installment amount must be positive")


@dataclass(frozen=True, slots=True)
class Contract:
    id: UUID
    client_folder_id: UUID
    total_amount_cents: int
    deposit_amount_cents: int
    balance_amount_cents: int
    installment_count: int
    signal_paid_on: date
    status: ContractStatus
    cancelled_at: datetime | None
    installments: tuple[ContractInstallment, ...]
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID) or not isinstance(self.client_folder_id, UUID):
            raise ValueError("contract identifiers must be UUIDs")
        if self.deposit_amount_cents != FIXED_DEPOSIT_CENTS:
            raise ValueError("contract deposit must be the fixed R$ 2,000.00")
        if self.total_amount_cents <= self.deposit_amount_cents:
            raise ValueError("contract total must exceed the fixed deposit")
        if self.balance_amount_cents != (
            self.total_amount_cents - self.deposit_amount_cents
        ):
            raise ValueError("contract balance is inconsistent")
        if self.installment_count != len(self.installments):
            raise ValueError("contract installment count is inconsistent")
        if (
            sum(item.amount_cents for item in self.installments)
            != self.balance_amount_cents
        ):
            raise ValueError("contract installments do not close the balance")
        if [item.number for item in self.installments] != list(
            range(1, self.installment_count + 1)
        ):
            raise ValueError("contract installments must be sequential")
        if (self.status is ContractStatus.CANCELLED) != (self.cancelled_at is not None):
            raise ValueError("contract cancellation state is inconsistent")
        if self.status is ContractStatus.PAID and any(
            item.paid_on is None for item in self.installments
        ):
            raise ValueError("paid contract cannot contain an unpaid installment")

    def is_overdue(self, *, as_of: date) -> bool:
        return self.status is ContractStatus.ACTIVE and any(
            item.paid_on is None and item.due_date < as_of for item in self.installments
        )


def _anchored_due_date(signal_paid_on: date, installment_number: int) -> date:
    """Avança meses pela âncora; data inexistente vira o 1º do mês seguinte."""
    absolute_month = signal_paid_on.year * 12 + signal_paid_on.month - 1
    target_month = absolute_month + installment_number
    year, zero_based_month = divmod(target_month, 12)
    month = zero_based_month + 1
    if year > date.max.year:
        raise ValueError("installment schedule exceeds the supported date range")
    if signal_paid_on.day <= monthrange(year, month)[1]:
        return date(year, month, signal_paid_on.day)

    next_absolute_month = target_month + 1
    next_year, next_zero_based_month = divmod(next_absolute_month, 12)
    if next_year > date.max.year:
        raise ValueError("installment schedule exceeds the supported date range")
    return date(next_year, next_zero_based_month + 1, 1)


def build_installment_plan(
    *, total_amount_cents: int, installment_count: int, signal_paid_on: date
) -> tuple[InstallmentPlanItem, ...]:
    """Divide o saldo em centavos e aplica a recorrência civil homologada."""
    if total_amount_cents <= FIXED_DEPOSIT_CENTS:
        raise ValueError("contract total must exceed the fixed deposit")
    if not 1 <= installment_count <= MAX_INSTALLMENTS:
        raise ValueError(f"installment count must be between 1 and {MAX_INSTALLMENTS}")

    balance = total_amount_cents - FIXED_DEPOSIT_CENTS
    base_amount, remainder = divmod(balance, installment_count)
    if base_amount < 1:
        raise ValueError(
            "contract balance must allow at least one cent per installment"
        )

    return tuple(
        InstallmentPlanItem(
            number=number,
            amount_cents=base_amount + (1 if number <= remainder else 0),
            due_date=_anchored_due_date(signal_paid_on, number),
        )
        for number in range(1, installment_count + 1)
    )
