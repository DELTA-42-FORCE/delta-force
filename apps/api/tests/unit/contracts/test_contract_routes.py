"""Contrato HTTP autenticado do módulo de contratos."""

from collections.abc import Iterator
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from crm_api.domain.auth.entities import User
from crm_api.domain.contracts.entities import (
    FIXED_DEPOSIT_CENTS,
    Contract,
    ContractInstallment,
    ContractStatus,
)
from crm_api.main import app
from crm_api.presentation.auth import dependencies as auth_dependencies
from crm_api.presentation.contracts import dependencies as contract_dependencies

OWNER = User(
    id=UUID("00000000-0000-0000-0000-000000000029"),
    email="owner-contracts@deltaforce.internal",
    full_name="Owner Contracts Synthetic",
    password_hash="not-returned",
    is_active=True,
)
CLIENT_ID = UUID("00000000-0000-0000-0000-000000000030")
CONTRACT_ID = UUID("00000000-0000-0000-0000-000000000031")
INSTALLMENT_ID = UUID("00000000-0000-0000-0000-000000000032")


def _contract(
    status: ContractStatus = ContractStatus.ACTIVE, paid: bool = False
) -> Contract:
    now = datetime(2026, 9, 19, 12, tzinfo=UTC)
    return Contract(
        id=CONTRACT_ID,
        client_folder_id=CLIENT_ID,
        total_amount_cents=300_000,
        deposit_amount_cents=FIXED_DEPOSIT_CENTS,
        balance_amount_cents=100_000,
        installment_count=1,
        signal_paid_on=date(2026, 8, 10),
        status=status,
        cancelled_at=now if status is ContractStatus.CANCELLED else None,
        installments=(
            ContractInstallment(
                id=INSTALLMENT_ID,
                number=1,
                amount_cents=100_000,
                due_date=date(2026, 9, 10),
                paid_on=date(2026, 9, 10) if paid else None,
            ),
        ),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def contract_client() -> Iterator[tuple[TestClient, dict[str, AsyncMock]]]:
    calls = {
        "create": AsyncMock(return_value=_contract()),
        "list": AsyncMock(return_value=[_contract()]),
        "payment": AsyncMock(
            return_value=_contract(status=ContractStatus.PAID, paid=True)
        ),
        "cancel": AsyncMock(return_value=_contract(ContractStatus.CANCELLED)),
    }
    app.dependency_overrides[auth_dependencies.get_current_user] = lambda: OWNER
    app.dependency_overrides[contract_dependencies.get_create_contract_use_case] = (
        lambda: SimpleNamespace(execute=calls["create"])
    )
    app.dependency_overrides[
        contract_dependencies.get_list_client_contracts_use_case
    ] = lambda: SimpleNamespace(execute=calls["list"])
    app.dependency_overrides[
        contract_dependencies.get_record_installment_payment_use_case
    ] = lambda: SimpleNamespace(execute=calls["payment"])
    app.dependency_overrides[contract_dependencies.get_cancel_contract_use_case] = (
        lambda: SimpleNamespace(execute=calls["cancel"])
    )
    try:
        with TestClient(app) as client:
            yield client, calls
    finally:
        app.dependency_overrides.clear()


def test_contract_routes_preserve_exact_money_and_lifecycle(
    contract_client: tuple[TestClient, dict[str, AsyncMock]],
) -> None:
    client, calls = contract_client

    created = client.post(
        f"/clients/{CLIENT_ID}/contracts",
        json={
            "total_amount": "3000.00",
            "installment_count": 1,
            "signal_paid_on": "2026-08-10",
        },
    )
    listed = client.get(f"/clients/{CLIENT_ID}/contracts")
    paid = client.post(
        f"/clients/{CLIENT_ID}/contracts/{CONTRACT_ID}/installments/"
        f"{INSTALLMENT_ID}/payments",
        json={"paid_on": "2026-09-10"},
    )
    cancelled = client.post(f"/clients/{CLIENT_ID}/contracts/{CONTRACT_ID}/cancel")

    assert created.status_code == 201
    assert created.json()["total_amount_cents"] == 300_000
    assert created.json()["is_overdue"] is True
    assert listed.status_code == 200
    assert paid.json()["status"] == "paid"
    assert cancelled.json()["status"] == "cancelled"
    assert calls["create"].await_args.kwargs["total_amount_cents"] == 300_000
    calls["list"].assert_awaited_once()
    calls["payment"].assert_awaited_once()
    calls["cancel"].assert_awaited_once()


def test_contract_creation_rejects_total_without_a_balance(
    contract_client: tuple[TestClient, dict[str, AsyncMock]],
) -> None:
    client, calls = contract_client

    response = client.post(
        f"/clients/{CLIENT_ID}/contracts",
        json={
            "total_amount": "2000.00",
            "installment_count": 1,
            "signal_paid_on": "2026-08-10",
        },
    )

    assert response.status_code == 422
    calls["create"].assert_not_awaited()
