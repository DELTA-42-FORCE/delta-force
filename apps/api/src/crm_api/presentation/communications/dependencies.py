"""Fiação dos casos de uso de comunicação."""

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.communications.list_recipient_candidates import (
    ListRecipientCandidatesUseCase,
)
from crm_api.application.communications.templates import (
    CreateMessageTemplateUseCase,
    DeleteMessageTemplateUseCase,
    ListMessageTemplatesUseCase,
    UpdateMessageTemplateUseCase,
)
from crm_api.infrastructure.audit.repositories import SqlAlchemyAuditEventRepository
from crm_api.infrastructure.audit.transactions import SqlAlchemyTransaction
from crm_api.infrastructure.communications.repositories import (
    SqlAlchemyCommunicationRepository,
)
from crm_api.presentation.dependencies import DatabaseSession


def _repository(session: DatabaseSession) -> SqlAlchemyCommunicationRepository:
    return SqlAlchemyCommunicationRepository(session)


def get_create_message_template_use_case(
    session: DatabaseSession,
) -> CreateMessageTemplateUseCase:
    return CreateMessageTemplateUseCase(
        repository=_repository(session),
        audit=RecordAuditEventUseCase(SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )


def get_list_message_templates_use_case(
    session: DatabaseSession,
) -> ListMessageTemplatesUseCase:
    return ListMessageTemplatesUseCase(repository=_repository(session))


def get_update_message_template_use_case(
    session: DatabaseSession,
) -> UpdateMessageTemplateUseCase:
    return UpdateMessageTemplateUseCase(
        repository=_repository(session),
        audit=RecordAuditEventUseCase(SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )


def get_delete_message_template_use_case(
    session: DatabaseSession,
) -> DeleteMessageTemplateUseCase:
    return DeleteMessageTemplateUseCase(
        repository=_repository(session),
        audit=RecordAuditEventUseCase(SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )


def get_list_recipient_candidates_use_case(
    session: DatabaseSession,
) -> ListRecipientCandidatesUseCase:
    return ListRecipientCandidatesUseCase(repository=_repository(session))
