"""Fiação dos casos de uso de contratos."""

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.contracts.manage_contracts import (
    CancelContractUseCase,
    CreateContractUseCase,
    ListClientContractsUseCase,
    RecordInstallmentPaymentUseCase,
)
from crm_api.infrastructure.audit.repositories import SqlAlchemyAuditEventRepository
from crm_api.infrastructure.audit.transactions import SqlAlchemyTransaction
from crm_api.infrastructure.clients.repositories import SqlAlchemyClientFolderRepository
from crm_api.infrastructure.contracts.repositories import SqlAlchemyContractRepository
from crm_api.presentation.dependencies import DatabaseSession


def _audit(session: DatabaseSession) -> RecordAuditEventUseCase:
    return RecordAuditEventUseCase(events=SqlAlchemyAuditEventRepository(session))


def get_create_contract_use_case(session: DatabaseSession) -> CreateContractUseCase:
    return CreateContractUseCase(
        clients=SqlAlchemyClientFolderRepository(session),
        contracts=SqlAlchemyContractRepository(session),
        audit=_audit(session),
        transaction=SqlAlchemyTransaction(session),
    )


def get_list_client_contracts_use_case(
    session: DatabaseSession,
) -> ListClientContractsUseCase:
    return ListClientContractsUseCase(
        clients=SqlAlchemyClientFolderRepository(session),
        contracts=SqlAlchemyContractRepository(session),
        audit=_audit(session),
        transaction=SqlAlchemyTransaction(session),
    )


def get_record_installment_payment_use_case(
    session: DatabaseSession,
) -> RecordInstallmentPaymentUseCase:
    return RecordInstallmentPaymentUseCase(
        contracts=SqlAlchemyContractRepository(session),
        audit=_audit(session),
        transaction=SqlAlchemyTransaction(session),
    )


def get_cancel_contract_use_case(session: DatabaseSession) -> CancelContractUseCase:
    return CancelContractUseCase(
        contracts=SqlAlchemyContractRepository(session),
        audit=_audit(session),
        transaction=SqlAlchemyTransaction(session),
    )
