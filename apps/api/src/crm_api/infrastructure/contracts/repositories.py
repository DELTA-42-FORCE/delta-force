"""Adaptador SQLAlchemy da porta de contratos."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from crm_api.domain.contracts.entities import (
    FIXED_DEPOSIT_CENTS,
    Contract,
    ContractInstallment,
    ContractStatus,
    InstallmentPlanItem,
)
from crm_api.infrastructure.contracts.models import (
    ContractInstallmentModel,
    ContractModel,
)
from crm_api.infrastructure.timestamps import as_utc


def _to_contract(model: ContractModel) -> Contract:
    installments = tuple(
        ContractInstallment(
            id=item.id,
            number=item.number,
            amount_cents=item.amount_cents,
            due_date=item.due_date,
            paid_on=item.paid_on,
        )
        for item in sorted(model.installments, key=lambda item: item.number)
    )
    return Contract(
        id=model.id,
        client_folder_id=model.client_folder_id,
        total_amount_cents=model.total_amount_cents,
        deposit_amount_cents=model.deposit_amount_cents,
        balance_amount_cents=model.balance_amount_cents,
        installment_count=model.installment_count,
        signal_paid_on=model.signal_paid_on,
        status=ContractStatus(model.status),
        cancelled_at=(as_utc(model.cancelled_at) if model.cancelled_at else None),
        installments=installments,
        created_at=as_utc(model.created_at),
        updated_at=as_utc(model.updated_at),
    )


@dataclass(frozen=True, slots=True)
class SqlAlchemyContractRepository:
    session: AsyncSession

    async def create(
        self,
        *,
        client_folder_id: UUID,
        total_amount_cents: int,
        signal_paid_on: date,
        plan: Sequence[InstallmentPlanItem],
    ) -> Contract:
        model = ContractModel(
            client_folder_id=client_folder_id,
            total_amount_cents=total_amount_cents,
            deposit_amount_cents=FIXED_DEPOSIT_CENTS,
            balance_amount_cents=total_amount_cents - FIXED_DEPOSIT_CENTS,
            installment_count=len(plan),
            signal_paid_on=signal_paid_on,
            status=ContractStatus.ACTIVE.value,
            installments=[
                ContractInstallmentModel(
                    number=item.number,
                    amount_cents=item.amount_cents,
                    due_date=item.due_date,
                )
                for item in plan
            ],
        )
        self.session.add(model)
        await self.session.flush()
        return _to_contract(model)

    async def list_for_client(self, *, client_folder_id: UUID) -> list[Contract]:
        statement = (
            select(ContractModel)
            .options(selectinload(ContractModel.installments))
            .where(ContractModel.client_folder_id == client_folder_id)
            .order_by(ContractModel.created_at.desc(), ContractModel.id.desc())
        )
        models = (await self.session.scalars(statement)).all()
        return [_to_contract(model) for model in models]

    async def get_for_client(
        self, *, client_folder_id: UUID, contract_id: UUID, for_update: bool = False
    ) -> Contract | None:
        statement = (
            select(ContractModel)
            .options(selectinload(ContractModel.installments))
            .where(
                ContractModel.id == contract_id,
                ContractModel.client_folder_id == client_folder_id,
            )
        )
        if for_update:
            statement = statement.with_for_update()
        model = await self.session.scalar(statement)
        return _to_contract(model) if model is not None else None

    async def record_payment(
        self,
        *,
        contract_id: UUID,
        installment_id: UUID,
        paid_on: date,
        completes_contract: bool,
    ) -> Contract:
        statement = (
            select(ContractModel)
            .options(selectinload(ContractModel.installments))
            .where(ContractModel.id == contract_id)
            .with_for_update()
        )
        model = await self.session.scalar(statement)
        if model is None:
            raise RuntimeError("locked contract disappeared")
        installment = next(
            (item for item in model.installments if item.id == installment_id), None
        )
        if installment is None:
            raise RuntimeError("locked installment disappeared")
        installment.paid_on = paid_on
        if completes_contract:
            model.status = ContractStatus.PAID.value
        model.updated_at = datetime.now(UTC)
        await self.session.flush()
        return _to_contract(model)

    async def cancel(self, *, contract_id: UUID, cancelled_at: datetime) -> Contract:
        statement = (
            select(ContractModel)
            .options(selectinload(ContractModel.installments))
            .where(ContractModel.id == contract_id)
            .with_for_update()
        )
        model = await self.session.scalar(statement)
        if model is None:
            raise RuntimeError("locked contract disappeared")
        model.status = ContractStatus.CANCELLED.value
        model.cancelled_at = cancelled_at
        model.updated_at = cancelled_at
        await self.session.flush()
        return _to_contract(model)
