"""Porta de persistência de contratos."""

from datetime import date, datetime
from typing import Protocol, Sequence
from uuid import UUID

from crm_api.domain.contracts.entities import Contract, InstallmentPlanItem


class ContractRepository(Protocol):
    async def create(
        self,
        *,
        client_folder_id: UUID,
        total_amount_cents: int,
        signal_paid_on: date,
        plan: Sequence[InstallmentPlanItem],
    ) -> Contract: ...

    async def list_for_client(self, *, client_folder_id: UUID) -> list[Contract]: ...

    async def get_for_client(
        self, *, client_folder_id: UUID, contract_id: UUID, for_update: bool = False
    ) -> Contract | None: ...

    async def record_payment(
        self,
        *,
        contract_id: UUID,
        installment_id: UUID,
        paid_on: date,
        completes_contract: bool,
    ) -> Contract: ...

    async def cancel(
        self, *, contract_id: UUID, cancelled_at: datetime
    ) -> Contract: ...
