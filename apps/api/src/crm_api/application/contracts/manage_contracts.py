"""Casos de uso transacionais do parcelamento de contratos."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.transactions import Transaction
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.clients.errors import ClientFolderNotFoundError
from crm_api.domain.clients.repositories import ClientFolderRepository
from crm_api.domain.contracts.entities import (
    Contract,
    ContractStatus,
    build_installment_plan,
)
from crm_api.domain.contracts.errors import (
    ContractNotActiveError,
    ContractNotFoundError,
    InstallmentAlreadyPaidError,
    InstallmentNotFoundError,
)
from crm_api.domain.contracts.repositories import ContractRepository


@dataclass(frozen=True, slots=True)
class CreateContractUseCase:
    clients: ClientFolderRepository
    contracts: ContractRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        client_folder_id: UUID,
        total_amount_cents: int,
        installment_count: int,
        signal_paid_on: date,
        today: date | None = None,
    ) -> Contract:
        if signal_paid_on > (today or date.today()):
            raise ValueError("signal payment date cannot be in the future")
        if await self.clients.get(id=client_folder_id) is None:
            raise ClientFolderNotFoundError
        plan = build_installment_plan(
            total_amount_cents=total_amount_cents,
            installment_count=installment_count,
            signal_paid_on=signal_paid_on,
        )
        try:
            contract = await self.contracts.create(
                client_folder_id=client_folder_id,
                total_amount_cents=total_amount_cents,
                signal_paid_on=signal_paid_on,
                plan=plan,
            )
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.CONTRACT_CREATED,
                resource_type=AuditResourceType.CONTRACT,
                resource_id=str(contract.id),
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return contract


@dataclass(frozen=True, slots=True)
class ListClientContractsUseCase:
    clients: ClientFolderRepository
    contracts: ContractRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self, *, actor_user_id: UUID, client_folder_id: UUID
    ) -> list[Contract]:
        if await self.clients.get(id=client_folder_id) is None:
            raise ClientFolderNotFoundError
        try:
            contracts = await self.contracts.list_for_client(
                client_folder_id=client_folder_id
            )
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.CONTRACT_VIEWED,
                resource_type=AuditResourceType.CLIENT_FOLDER,
                resource_id=str(client_folder_id),
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return contracts


@dataclass(frozen=True, slots=True)
class RecordInstallmentPaymentUseCase:
    contracts: ContractRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        client_folder_id: UUID,
        contract_id: UUID,
        installment_id: UUID,
        paid_on: date,
        today: date | None = None,
    ) -> Contract:
        contract = await self.contracts.get_for_client(
            client_folder_id=client_folder_id,
            contract_id=contract_id,
            for_update=True,
        )
        if contract is None:
            raise ContractNotFoundError
        if contract.status is not ContractStatus.ACTIVE:
            raise ContractNotActiveError
        installment = next(
            (item for item in contract.installments if item.id == installment_id), None
        )
        if installment is None:
            raise InstallmentNotFoundError
        if installment.paid_on is not None:
            raise InstallmentAlreadyPaidError
        if paid_on < contract.signal_paid_on:
            raise ValueError("installment payment cannot predate the signal")
        if paid_on > (today or date.today()):
            raise ValueError("installment payment date cannot be in the future")

        completes_contract = all(
            item.id == installment_id or item.paid_on is not None
            for item in contract.installments
        )
        try:
            updated = await self.contracts.record_payment(
                contract_id=contract.id,
                installment_id=installment_id,
                paid_on=paid_on,
                completes_contract=completes_contract,
            )
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.CONTRACT_INSTALLMENT_PAID,
                resource_type=AuditResourceType.CONTRACT,
                resource_id=str(contract.id),
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return updated


@dataclass(frozen=True, slots=True)
class CancelContractUseCase:
    contracts: ContractRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self, *, actor_user_id: UUID, client_folder_id: UUID, contract_id: UUID
    ) -> Contract:
        contract = await self.contracts.get_for_client(
            client_folder_id=client_folder_id,
            contract_id=contract_id,
            for_update=True,
        )
        if contract is None:
            raise ContractNotFoundError
        if contract.status is not ContractStatus.ACTIVE:
            raise ContractNotActiveError
        now = datetime.now(UTC)
        try:
            updated = await self.contracts.cancel(
                contract_id=contract.id, cancelled_at=now
            )
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.CONTRACT_CANCELLED,
                resource_type=AuditResourceType.CONTRACT,
                resource_id=str(contract.id),
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return updated
