"""Fiação dos casos de uso de comunicação."""

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.communications.list_recipient_candidates import (
    ListRecipientCandidatesUseCase,
)
from crm_api.application.communications.email_delivery import (
    ConfigureEmailSenderUseCase,
    GetEmailSenderSettingsUseCase,
    ListEmailDispatchesUseCase,
    SendEmailBatchUseCase,
)
from crm_api.application.communications.render_template import (
    RenderMessageTemplateUseCase,
)
from crm_api.application.communications.templates import (
    CreateMessageTemplateUseCase,
    DeleteMessageTemplateUseCase,
    GetMessageTemplateUseCase,
    ListMessageTemplatesUseCase,
    UpdateMessageTemplateUseCase,
)
from crm_api.infrastructure.audit.repositories import SqlAlchemyAuditEventRepository
from crm_api.infrastructure.audit.transactions import SqlAlchemyTransaction
from crm_api.infrastructure.clients.repositories import SqlAlchemyClientFolderRepository
from crm_api.infrastructure.communications.repositories import (
    SqlAlchemyCommunicationRepository,
)
from crm_api.infrastructure.communications.smtp_sender import SmtpEmailSender
from crm_api.core.config import get_settings
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


def get_get_message_template_use_case(
    session: DatabaseSession,
) -> GetMessageTemplateUseCase:
    return GetMessageTemplateUseCase(repository=_repository(session))


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
    return ListRecipientCandidatesUseCase(
        repository=_repository(session),
        audit=RecordAuditEventUseCase(SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )


def get_render_message_template_use_case(
    session: DatabaseSession,
) -> RenderMessageTemplateUseCase:
    return RenderMessageTemplateUseCase(
        templates=_repository(session),
        clients=SqlAlchemyClientFolderRepository(session),
    )


def get_configure_email_sender_use_case(
    session: DatabaseSession,
) -> ConfigureEmailSenderUseCase:
    return ConfigureEmailSenderUseCase(
        repository=_repository(session),
        audit=RecordAuditEventUseCase(SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )


def get_email_sender_settings_use_case(
    session: DatabaseSession,
) -> GetEmailSenderSettingsUseCase:
    return GetEmailSenderSettingsUseCase(
        repository=_repository(session),
        audit=RecordAuditEventUseCase(SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )


def get_send_email_batch_use_case(
    session: DatabaseSession,
) -> SendEmailBatchUseCase:
    return SendEmailBatchUseCase(
        communications=_repository(session),
        clients=SqlAlchemyClientFolderRepository(session),
        sender=SmtpEmailSender(
            allow_insecure_local_smtp=get_settings().allow_insecure_local_smtp
        ),
        audit=RecordAuditEventUseCase(SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )


def get_list_email_dispatches_use_case(
    session: DatabaseSession,
) -> ListEmailDispatchesUseCase:
    return ListEmailDispatchesUseCase(
        repository=_repository(session),
        audit=RecordAuditEventUseCase(SqlAlchemyAuditEventRepository(session)),
        transaction=SqlAlchemyTransaction(session),
    )
