"""Configuração, envio individual rastreável e histórico da mala direta."""

from dataclasses import dataclass
import re
from uuid import UUID, uuid4

from email_validator import EmailNotValidError, validate_email

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.transactions import Transaction
from crm_api.domain.audit.entities import (
    AuditAction,
    AuditActorKind,
    AuditResourceType,
    AuditResult,
)
from crm_api.domain.clients.repositories import ClientFolderRepository
from crm_api.domain.communications.entities import (
    EmailDeliveryStatus,
    EmailDispatch,
    EmailDispatchCursor,
    EmailSenderSettings,
    OutboundEmail,
    SmtpSecurity,
)
from crm_api.domain.communications.errors import MessageTemplateNotFoundError
from crm_api.domain.communications.repositories import (
    CommunicationRepository,
    EmailSender,
)

_HOST_PATTERN = re.compile(r"^[A-Za-z0-9.-]+$")


class EmailSenderNotConfiguredError(Exception):
    pass


def normalize_sender_settings(
    *,
    sender_name: str,
    sender_email: str,
    smtp_host: str,
    smtp_port: int,
    security: SmtpSecurity,
    username: str | None,
    max_recipients: int,
) -> EmailSenderSettings:
    name = " ".join(sender_name.split())
    if not name or len(name) > 120:
        raise ValueError("sender name must contain between 1 and 120 characters")
    try:
        address = validate_email(
            sender_email.strip(), check_deliverability=False
        ).normalized
    except (AttributeError, EmailNotValidError):
        raise ValueError("sender email is invalid") from None
    host = smtp_host.strip().lower()
    if not host or len(host) > 253 or _HOST_PATTERN.fullmatch(host) is None:
        raise ValueError("SMTP host is invalid")
    if not isinstance(smtp_port, int) or not 1 <= smtp_port <= 65535:
        raise ValueError("SMTP port must be between 1 and 65535")
    if not isinstance(security, SmtpSecurity):
        raise ValueError("SMTP security is invalid")
    normalized_username = username.strip() if isinstance(username, str) else None
    if normalized_username == "":
        normalized_username = None
    if normalized_username is not None and len(normalized_username) > 320:
        raise ValueError("SMTP username is too long")
    if not isinstance(max_recipients, int) or not 1 <= max_recipients <= 100:
        raise ValueError("max recipients must be between 1 and 100")
    return EmailSenderSettings(
        sender_name=name,
        sender_email=address,
        smtp_host=host,
        smtp_port=smtp_port,
        security=security,
        username=normalized_username,
        max_recipients=max_recipients,
    )


@dataclass(frozen=True, slots=True)
class ConfigureEmailSenderUseCase:
    repository: CommunicationRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        sender_name: str,
        sender_email: str,
        smtp_host: str,
        smtp_port: int,
        security: SmtpSecurity,
        username: str | None,
        max_recipients: int,
    ) -> EmailSenderSettings:
        settings = normalize_sender_settings(
            sender_name=sender_name,
            sender_email=sender_email,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            security=security,
            username=username,
            max_recipients=max_recipients,
        )
        try:
            saved = await self.repository.save_sender_settings(settings=settings)
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.EMAIL_SENDER_SETTINGS_UPDATED,
                resource_type=AuditResourceType.EMAIL_SENDER_SETTINGS,
                resource_id=None,
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return saved


@dataclass(frozen=True, slots=True)
class GetEmailSenderSettingsUseCase:
    repository: CommunicationRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(self, *, actor_user_id: UUID) -> EmailSenderSettings:
        try:
            settings = await self.repository.get_sender_settings()
            if settings is None:
                raise EmailSenderNotConfiguredError
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.EMAIL_SENDER_SETTINGS_VIEWED,
                resource_type=AuditResourceType.EMAIL_SENDER_SETTINGS,
                resource_id=None,
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return settings


@dataclass(frozen=True, slots=True)
class EmailDispatchPage:
    items: tuple[EmailDispatch, ...]
    next_cursor: EmailDispatchCursor | None


@dataclass(frozen=True, slots=True)
class ListEmailDispatchesUseCase:
    repository: CommunicationRepository
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        limit: int,
        before: EmailDispatchCursor | None,
    ) -> EmailDispatchPage:
        if not 1 <= limit <= 100:
            raise ValueError("email dispatch limit must be between 1 and 100")
        try:
            items = await self.repository.list_dispatches(
                limit=limit + 1, before=before
            )
            page_items = tuple(items[:limit])
            next_cursor = (
                EmailDispatchCursor(
                    attempted_at=page_items[-1].attempted_at,
                    id=page_items[-1].id,
                )
                if len(items) > limit and page_items
                else None
            )
            await self.audit.execute(
                actor_kind=AuditActorKind.AUTHENTICATED,
                actor_user_id=actor_user_id,
                action=AuditAction.EMAIL_DISPATCH_HISTORY_VIEWED,
                resource_type=AuditResourceType.EMAIL_DISPATCH,
                resource_id=None,
                result=AuditResult.SUCCESS,
            )
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
        return EmailDispatchPage(items=page_items, next_cursor=next_cursor)


@dataclass(frozen=True, slots=True)
class SendEmailBatchUseCase:
    communications: CommunicationRepository
    clients: ClientFolderRepository
    sender: EmailSender
    audit: RecordAuditEventUseCase
    transaction: Transaction

    async def execute(
        self,
        *,
        actor_user_id: UUID,
        template_id: UUID,
        client_ids: list[UUID],
        credential: str | None,
        confirm_repeat: bool,
    ) -> tuple[EmailDispatch, ...]:
        settings = await self.communications.get_sender_settings()
        if settings is None:
            raise EmailSenderNotConfiguredError
        if not client_ids or len(client_ids) > settings.max_recipients:
            raise ValueError(
                f"client_ids must contain between 1 and {settings.max_recipients} items"
            )
        if len(set(client_ids)) != len(client_ids):
            raise ValueError("client_ids must not contain duplicates")
        template = await self.communications.get_template(id=template_id)
        if template is None:
            raise MessageTemplateNotFoundError

        selected_clients = []
        for client_id in client_ids:
            client = await self.clients.get(id=client_id)
            if client is None:
                raise ValueError("one or more clients do not exist")
            selected_clients.append(client)

        results: list[EmailDispatch] = []
        for client in selected_clients:
            subject = template.subject.replace("{{nome}}", client.display_name)
            body = template.body.replace("{{nome}}", client.display_name)
            message_id = f"<{uuid4()}@delta-force.local>"

            if client.email is None:
                dispatch = await self.communications.create_dispatch(
                    template_id=template.id,
                    client_id=client.id,
                    recipient_email=None,
                    subject=subject,
                    body=body,
                    message_id=message_id,
                    status=EmailDeliveryStatus.MISSING_EMAIL,
                    detail="client_email_missing",
                )
                await self.transaction.commit()
                results.append(dispatch)
                continue

            requires_confirmation = (
                await self.communications.has_delivery_requiring_confirmation(
                    template_id=template.id, client_id=client.id
                )
            )
            if requires_confirmation and not confirm_repeat:
                dispatch = await self.communications.create_dispatch(
                    template_id=template.id,
                    client_id=client.id,
                    recipient_email=client.email,
                    subject=subject,
                    body=body,
                    message_id=message_id,
                    status=EmailDeliveryStatus.SKIPPED_DUPLICATE,
                    detail="repeat_confirmation_required",
                )
                await self.transaction.commit()
                results.append(dispatch)
                continue

            pending = await self.communications.create_dispatch(
                template_id=template.id,
                client_id=client.id,
                recipient_email=client.email,
                subject=subject,
                body=body,
                message_id=message_id,
                status=EmailDeliveryStatus.PENDING,
                detail=None,
            )
            await self.transaction.commit()
            delivery = await self.sender.send(
                settings=settings,
                message=OutboundEmail(
                    message_id=message_id,
                    recipient=client.email,
                    subject=subject,
                    body=body,
                ),
                credential=credential,
            )
            dispatch = await self.communications.update_dispatch_result(
                id=pending.id,
                status=delivery.status,
                detail=delivery.detail,
            )
            await self.transaction.commit()
            results.append(dispatch)

        await self.audit.execute(
            actor_kind=AuditActorKind.AUTHENTICATED,
            actor_user_id=actor_user_id,
            action=AuditAction.EMAIL_BATCH_SENT,
            resource_type=AuditResourceType.EMAIL_DISPATCH,
            resource_id=None,
            result=AuditResult.SUCCESS,
            context={
                "requested_count": str(len(client_ids)),
                "sent_count": str(
                    sum(item.status is EmailDeliveryStatus.SENT for item in results)
                ),
            },
        )
        await self.transaction.commit()
        return tuple(results)
