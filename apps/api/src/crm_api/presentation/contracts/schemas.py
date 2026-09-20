"""Contratos públicos do módulo financeiro."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from crm_api.domain.contracts.entities import MAX_INSTALLMENTS


class CreateContractRequest(BaseModel):
    total_amount: Decimal = Field(
        gt=Decimal("2000.00"), max_digits=14, decimal_places=2
    )
    installment_count: int = Field(ge=1, le=MAX_INSTALLMENTS)
    signal_paid_on: date


class RecordInstallmentPaymentRequest(BaseModel):
    paid_on: date


class ContractInstallmentResponse(BaseModel):
    id: UUID
    number: int
    amount_cents: int
    due_date: date
    paid_on: date | None


class ContractResponse(BaseModel):
    id: UUID
    client_folder_id: UUID
    total_amount_cents: int
    deposit_amount_cents: int
    balance_amount_cents: int
    installment_count: int
    signal_paid_on: date
    status: str
    is_overdue: bool
    cancelled_at: datetime | None
    installments: list[ContractInstallmentResponse]
    created_at: datetime
    updated_at: datetime
