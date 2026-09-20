"""Rotas autenticadas de contratos e parcelas."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from crm_api.application.contracts.manage_contracts import (
    CancelContractUseCase,
    CreateContractUseCase,
    ListClientContractsUseCase,
    RecordInstallmentPaymentUseCase,
)
from crm_api.domain.clients.errors import ClientFolderNotFoundError
from crm_api.domain.contracts.entities import Contract
from crm_api.domain.contracts.errors import (
    ContractNotActiveError,
    ContractNotFoundError,
    InstallmentAlreadyPaidError,
    InstallmentNotFoundError,
)
from crm_api.presentation.auth.dependencies import CurrentUser
from crm_api.presentation.contracts.dependencies import (
    get_cancel_contract_use_case,
    get_create_contract_use_case,
    get_list_client_contracts_use_case,
    get_record_installment_payment_use_case,
)
from crm_api.presentation.contracts.schemas import (
    ContractInstallmentResponse,
    ContractResponse,
    CreateContractRequest,
    RecordInstallmentPaymentRequest,
)

router = APIRouter(prefix="/clients/{client_id}/contracts", tags=["contracts"])


def _to_response(contract: Contract) -> ContractResponse:
    return ContractResponse(
        id=contract.id,
        client_folder_id=contract.client_folder_id,
        total_amount_cents=contract.total_amount_cents,
        deposit_amount_cents=contract.deposit_amount_cents,
        balance_amount_cents=contract.balance_amount_cents,
        installment_count=contract.installment_count,
        signal_paid_on=contract.signal_paid_on,
        status=contract.status.value,
        is_overdue=contract.is_overdue(as_of=date.today()),
        cancelled_at=contract.cancelled_at,
        installments=[
            ContractInstallmentResponse(
                id=item.id,
                number=item.number,
                amount_cents=item.amount_cents,
                due_date=item.due_date,
                paid_on=item.paid_on,
            )
            for item in contract.installments
        ],
        created_at=contract.created_at,
        updated_at=contract.updated_at,
    )


def _contract_error(error: Exception) -> HTTPException:
    if isinstance(error, (ClientFolderNotFoundError, ContractNotFoundError)):
        return HTTPException(status_code=404, detail="client or contract not found")
    if isinstance(error, InstallmentNotFoundError):
        return HTTPException(status_code=404, detail="installment not found")
    if isinstance(error, InstallmentAlreadyPaidError):
        return HTTPException(status_code=409, detail="installment already paid")
    if isinstance(error, ContractNotActiveError):
        return HTTPException(status_code=409, detail="contract is not active")
    return HTTPException(status_code=422, detail=str(error))


@router.post("", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def create_contract(
    client_id: UUID,
    payload: CreateContractRequest,
    current_user: CurrentUser,
    use_case: Annotated[CreateContractUseCase, Depends(get_create_contract_use_case)],
) -> ContractResponse:
    try:
        contract = await use_case.execute(
            actor_user_id=current_user.id,
            client_folder_id=client_id,
            total_amount_cents=int(payload.total_amount * 100),
            installment_count=payload.installment_count,
            signal_paid_on=payload.signal_paid_on,
        )
    except (ClientFolderNotFoundError, ValueError) as error:
        raise _contract_error(error) from None
    return _to_response(contract)


@router.get("", response_model=list[ContractResponse])
async def list_client_contracts(
    client_id: UUID,
    current_user: CurrentUser,
    use_case: Annotated[
        ListClientContractsUseCase, Depends(get_list_client_contracts_use_case)
    ],
) -> list[ContractResponse]:
    try:
        contracts = await use_case.execute(
            actor_user_id=current_user.id, client_folder_id=client_id
        )
    except ClientFolderNotFoundError as error:
        raise _contract_error(error) from None
    return [_to_response(contract) for contract in contracts]


@router.post(
    "/{contract_id}/installments/{installment_id}/payments",
    response_model=ContractResponse,
)
async def record_installment_payment(
    client_id: UUID,
    contract_id: UUID,
    installment_id: UUID,
    payload: RecordInstallmentPaymentRequest,
    current_user: CurrentUser,
    use_case: Annotated[
        RecordInstallmentPaymentUseCase,
        Depends(get_record_installment_payment_use_case),
    ],
) -> ContractResponse:
    try:
        contract = await use_case.execute(
            actor_user_id=current_user.id,
            client_folder_id=client_id,
            contract_id=contract_id,
            installment_id=installment_id,
            paid_on=payload.paid_on,
        )
    except (
        ContractNotFoundError,
        InstallmentNotFoundError,
        InstallmentAlreadyPaidError,
        ContractNotActiveError,
        ValueError,
    ) as error:
        raise _contract_error(error) from None
    return _to_response(contract)


@router.post("/{contract_id}/cancel", response_model=ContractResponse)
async def cancel_contract(
    client_id: UUID,
    contract_id: UUID,
    current_user: CurrentUser,
    use_case: Annotated[CancelContractUseCase, Depends(get_cancel_contract_use_case)],
) -> ContractResponse:
    try:
        contract = await use_case.execute(
            actor_user_id=current_user.id,
            client_folder_id=client_id,
            contract_id=contract_id,
        )
    except (ContractNotFoundError, ContractNotActiveError) as error:
        raise _contract_error(error) from None
    return _to_response(contract)
