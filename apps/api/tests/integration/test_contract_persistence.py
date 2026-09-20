"""Persistência SQLite dos contratos, pagamentos, estados e auditoria."""

from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.contracts.manage_contracts import (
    CancelContractUseCase,
    CreateContractUseCase,
    RecordInstallmentPaymentUseCase,
)
from crm_api.domain.contracts.entities import ContractStatus
from crm_api.infrastructure.audit.models import AuditEventModel
from crm_api.infrastructure.audit.repositories import SqlAlchemyAuditEventRepository
from crm_api.infrastructure.audit.transactions import SqlAlchemyTransaction
from crm_api.infrastructure.auth.models import UserModel
from crm_api.infrastructure.clients.models import ClientFolderModel
from crm_api.infrastructure.clients.repositories import SqlAlchemyClientFolderRepository
from crm_api.infrastructure.contracts.models import (
    ContractInstallmentModel,
    ContractModel,
)
from crm_api.infrastructure.contracts.repositories import SqlAlchemyContractRepository
from crm_api.infrastructure.database import get_engine, get_session_factory

pytestmark = pytest.mark.integration


def _requires_disposable_sqlite() -> None:
    engine = get_engine()
    if engine.dialect.name != "sqlite":
        pytest.skip("requires a sqlite+aiosqlite DATABASE_URL")
    database_path = Path(engine.url.database or "")
    if not database_path.stem.startswith("delta_force_integration_"):
        raise RuntimeError("refusing contract test on non-disposable SQLite database")


async def test_contract_lifecycle_persists_exact_values_and_audit() -> None:
    _requires_disposable_sqlite()
    owner_id = uuid4()
    contract_ids = []

    async with get_session_factory()() as session:
        session.add(
            UserModel(
                id=owner_id,
                email=f"finance-{owner_id}@deltaforce.internal",
                full_name="Proprietário Financeiro Sintético",
                password_hash="synthetic-password-hash",
            )
        )
        client = await SqlAlchemyClientFolderRepository(session).create(
            display_name="Cliente Financeiro Sintético", profile_data={}
        )
        await session.commit()

        contracts = SqlAlchemyContractRepository(session)
        audit = RecordAuditEventUseCase(events=SqlAlchemyAuditEventRepository(session))
        transaction = SqlAlchemyTransaction(session)
        create = CreateContractUseCase(
            clients=SqlAlchemyClientFolderRepository(session),
            contracts=contracts,
            audit=audit,
            transaction=transaction,
        )
        first = await create.execute(
            actor_user_id=owner_id,
            client_folder_id=client.id,
            total_amount_cents=1_200_003,
            installment_count=3,
            signal_paid_on=date(2026, 1, 31),
            today=date(2026, 9, 19),
        )
        contract_ids.append(first.id)

        assert [item.amount_cents for item in first.installments] == [
            333_335,
            333_334,
            333_334,
        ]
        assert [item.due_date for item in first.installments] == [
            date(2026, 3, 1),
            date(2026, 3, 31),
            date(2026, 5, 1),
        ]

        record_payment = RecordInstallmentPaymentUseCase(
            contracts=contracts, audit=audit, transaction=transaction
        )
        current = first
        for installment in first.installments:
            current = await record_payment.execute(
                actor_user_id=owner_id,
                client_folder_id=client.id,
                contract_id=first.id,
                installment_id=installment.id,
                paid_on=date(2026, 9, 10),
                today=date(2026, 9, 19),
            )
        assert current.status is ContractStatus.PAID
        assert all(item.paid_on == date(2026, 9, 10) for item in current.installments)

        second = await create.execute(
            actor_user_id=owner_id,
            client_folder_id=client.id,
            total_amount_cents=300_000,
            installment_count=1,
            signal_paid_on=date(2026, 8, 1),
            today=date(2026, 9, 19),
        )
        contract_ids.append(second.id)
        cancelled = await CancelContractUseCase(
            contracts=contracts, audit=audit, transaction=transaction
        ).execute(
            actor_user_id=owner_id,
            client_folder_id=client.id,
            contract_id=second.id,
        )
        assert cancelled.status is ContractStatus.CANCELLED
        assert cancelled.cancelled_at is not None

        actions = (
            await session.scalars(
                select(AuditEventModel.action)
                .where(AuditEventModel.actor_user_id == owner_id)
                .order_by(AuditEventModel.occurred_at.asc())
            )
        ).all()
        assert actions.count("contract.created") == 2
        assert actions.count("contract.installment_paid") == 3
        assert actions.count("contract.cancelled") == 1

        stored = await session.get(ContractModel, first.id)
        assert stored is not None
        assert stored.total_amount_cents == 1_200_003
        assert stored.status == "paid"

        await session.execute(
            delete(AuditEventModel).where(AuditEventModel.actor_user_id == owner_id)
        )
        await session.execute(
            delete(ContractInstallmentModel).where(
                ContractInstallmentModel.contract_id.in_(contract_ids)
            )
        )
        await session.execute(
            delete(ContractModel).where(ContractModel.id.in_(contract_ids))
        )
        await session.execute(
            delete(ClientFolderModel).where(ClientFolderModel.id == client.id)
        )
        await session.execute(delete(UserModel).where(UserModel.id == owner_id))
        await session.commit()
