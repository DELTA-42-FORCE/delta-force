"""Fiação HTTP dos casos de uso e adaptadores de auditoria."""

from crm_api.application.audit.list_audit_events import ListAuditEventsUseCase
from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.infrastructure.audit.repositories import (
    SqlAlchemyAuditEventRepository,
)
from crm_api.infrastructure.audit.transactions import SqlAlchemyTransaction
from crm_api.presentation.dependencies import DatabaseSession


def get_record_audit_event_use_case(
    session: DatabaseSession,
) -> RecordAuditEventUseCase:
    return RecordAuditEventUseCase(events=SqlAlchemyAuditEventRepository(session))


def get_list_audit_events_use_case(
    session: DatabaseSession,
) -> ListAuditEventsUseCase:
    repository = SqlAlchemyAuditEventRepository(session)
    return ListAuditEventsUseCase(
        events=repository,
        audit=RecordAuditEventUseCase(events=repository),
        transaction=SqlAlchemyTransaction(session),
    )


def get_audit_transaction(session: DatabaseSession) -> SqlAlchemyTransaction:
    return SqlAlchemyTransaction(session)
