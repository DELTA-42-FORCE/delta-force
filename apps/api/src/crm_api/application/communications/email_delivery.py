"""Configuração, envio individual rastreável e histórico da mala direta."""

import asyncio
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
_LOCAL_SMTP_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_EMAIL_BATCH_LOCK = asyncio.Lock()


class EmailSenderNotConfiguredError(Exception):
    pass


class RepeatConfirmationRequiredError(Exception):
    pass


class DeliveryAlreadyConfirmedError(Exception):
    pass


class DeliveryInProgressError(Exception):
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
    allow_insecure_local_smtp: bool = False,
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
    if security is SmtpSecurity.NONE_DEV and not (
        allow_insecure_local_smtp and host in _LOCAL_SMTP_HOSTS
    ):
        raise ValueError("insecure SMTP is restricted to local development")
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
    allow_insecure_local_smtp: bool = False

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
            allow_insecure_local_smtp=self.allow_insecure_local_smtp,
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
        # O aplicativo possui um único processo local. Serializar lotes fecha a
        # janela entre a verificação e a reserva `pending`, inclusive sob clique
        # duplo ou duas requisições concorrentes.
        async with _EMAIL_BATCH_LOCK:
            return await self._execute_locked(
                actor_user_id=actor_user_id,
                template_id=template_id,
                client_ids=client_ids,
                credential=credential,
                confirm_repeat=confirm_repeat,
            )

    async def _execute_locked(
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

        # The packaged app has one API process and this flow holds its batch lock.
        # A pending row visible here can only belong to an interrupted runtime.
        await self.communications.reconcile_stale_pending_dispatches(
            template_id=template.id,
            client_ids=[client.id for client in selected_clients],
        )
        await self.transaction.commit()

        barriers = {
            client.id: barrier
            for client in selected_clients
            if (
                barrier := await self.communications.latest_delivery_barrier(
                    template_id=template.id, client_id=client.id
                )
            )
            is not None
        }
        if any(
            barrier.status is EmailDeliveryStatus.SENT for barrier in barriers.values()
        ):
            raise DeliveryAlreadyConfirmedError
        if any(
            barrier.status is EmailDeliveryStatus.PENDING
            for barrier in barriers.values()
        ):
            raise DeliveryInProgressError
        if barriers and not confirm_repeat:
            raise RepeatConfirmationRequiredError

        results: list[EmailDispatch] = []
        await self.audit.execute(
            actor_kind=AuditActorKind.AUTHENTICATED,
            actor_user_id=actor_user_id,
            action=AuditAction.EMAIL_BATCH_STARTED,
            resource_type=AuditResourceType.EMAIL_DISPATCH,
            resource_id=None,
            result=AuditResult.SUCCESS,
            context={
                "phase": "started",
                "requested_count": str(len(client_ids)),
            },
        )
        await self.transaction.commit()
        try:
            for client in selected_clients:
                subject = template.subject.replace("{{nome}}", client.display_name)
                body = template.body.replace("{{nome}}", client.display_name)
                message_id = f"<{uuid4()}@delta-force.local>"
                retry_of = barriers.get(client.id)

                if client.email is None:
                    dispatch = await self.communications.create_dispatch(
                        template_id=template.id,
                        client_id=client.id,
                        recipient_email=None,
                        subject=subject,
                        body=body,
                        message_id=message_id,
                        retry_of_id=None,
                        retry_of_message_id=None,
                        status=EmailDeliveryStatus.MISSING_EMAIL,
                        detail="client_email_missing",
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
                    retry_of_id=retry_of.id if retry_of is not None else None,
                    retry_of_message_id=(
                        retry_of.message_id if retry_of is not None else None
                    ),
                    status=EmailDeliveryStatus.PENDING,
                    detail=None,
                )
                await self.transaction.commit()
                try:
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
                except BaseException:
                    uncertain = await self.communications.update_dispatch_result(
                        id=pending.id,
                        status=EmailDeliveryStatus.UNKNOWN,
                        detail="sender_interrupted",
                    )
                    await self.transaction.commit()
                    results.append(uncertain)
                    raise
                dispatch = await self.communications.update_dispatch_result(
                    id=pending.id,
                    status=delivery.status,
                    detail=delivery.detail,
                )
                await self.transaction.commit()
                results.append(dispatch)
        except BaseException:
            await self.transaction.rollback()
            await self._audit_completion(
                actor_user_id=actor_user_id,
                requested_count=len(client_ids),
                results=results,
                forced_failure=True,
            )
            raise
        await self._audit_completion(
            actor_user_id=actor_user_id,
            requested_count=len(client_ids),
            results=results,
            forced_failure=False,
        )
        return tuple(results)

    async def _audit_completion(
        self,
        *,
        actor_user_id: UUID,
        requested_count: int,
        results: list[EmailDispatch],
        forced_failure: bool,
    ) -> None:
        counts = {
            status: sum(item.status is status for item in results)
            for status in EmailDeliveryStatus
        }
        unsuccessful = sum(
            counts[status]
            for status in (
                EmailDeliveryStatus.REJECTED,
                EmailDeliveryStatus.UNKNOWN,
                EmailDeliveryStatus.PENDING,
                EmailDeliveryStatus.MISSING_EMAIL,
            )
        )
        await self.audit.execute(
            actor_kind=AuditActorKind.AUTHENTICATED,
            actor_user_id=actor_user_id,
            action=(
                AuditAction.EMAIL_BATCH_FAILED
                if forced_failure
                else AuditAction.EMAIL_BATCH_COMPLETED
            ),
            resource_type=AuditResourceType.EMAIL_DISPATCH,
            resource_id=None,
            result=(
                AuditResult.FAILURE
                if forced_failure or unsuccessful > 0
                else AuditResult.SUCCESS
            ),
            context={
                "phase": "failed" if forced_failure else "completed",
                "requested_count": str(requested_count),
                "sent_count": str(counts[EmailDeliveryStatus.SENT]),
                "rejected_count": str(counts[EmailDeliveryStatus.REJECTED]),
                "unknown_count": str(counts[EmailDeliveryStatus.UNKNOWN]),
                "missing_email_count": str(counts[EmailDeliveryStatus.MISSING_EMAIL]),
            },
        )
        await self.transaction.commit()
