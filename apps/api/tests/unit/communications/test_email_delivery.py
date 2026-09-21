from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
import smtplib
import ssl
from uuid import UUID, uuid4

import pytest

from crm_api.application.audit.record_audit_event import RecordAuditEventUseCase
from crm_api.application.communications.email_delivery import (
    DeliveryAlreadyConfirmedError,
    ConfigureEmailSenderUseCase,
    RepeatConfirmationRequiredError,
    SendEmailBatchUseCase,
    normalize_sender_settings,
)
from crm_api.domain.audit.entities import AuditEvent, AuditResult
from crm_api.domain.clients.entities import ClientFolder
from crm_api.domain.communications.entities import (
    EmailDeliveryResult,
    EmailDeliveryStatus,
    EmailDispatch,
    EmailSenderSettings,
    MessageTemplate,
    OutboundEmail,
    SmtpSecurity,
)
from crm_api.infrastructure.communications.smtp_sender import SmtpEmailSender


@dataclass
class FakeAudit:
    events: list[AuditEvent] = field(default_factory=list)

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)


@dataclass
class FakeTransaction:
    commits: int = 0
    rollbacks: int = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


@dataclass
class FakeClients:
    items: dict[UUID, ClientFolder]

    async def get(self, *, id: UUID) -> ClientFolder | None:
        return self.items.get(id)


@dataclass
class FakeSender:
    result: EmailDeliveryResult
    messages: list[OutboundEmail] = field(default_factory=list)
    credentials: list[str | None] = field(default_factory=list)

    async def send(
        self,
        *,
        settings: EmailSenderSettings,
        message: OutboundEmail,
        credential: str | None,
    ) -> EmailDeliveryResult:
        del settings
        self.messages.append(message)
        self.credentials.append(credential)
        return self.result


@dataclass
class FakeCommunications:
    settings: EmailSenderSettings | None
    template: MessageTemplate | None
    dispatches: list[EmailDispatch] = field(default_factory=list)

    async def get_sender_settings(self) -> EmailSenderSettings | None:
        return self.settings

    async def save_sender_settings(
        self, *, settings: EmailSenderSettings
    ) -> EmailSenderSettings:
        self.settings = settings
        return settings

    async def get_template(self, *, id: UUID) -> MessageTemplate | None:
        if self.template is not None and self.template.id == id:
            return self.template
        return None

    async def create_dispatch(
        self,
        *,
        template_id: UUID,
        client_id: UUID,
        recipient_email: str | None,
        subject: str,
        body: str,
        message_id: str,
        retry_of_id: UUID | None,
        retry_of_message_id: str | None,
        status: EmailDeliveryStatus,
        detail: str | None,
    ) -> EmailDispatch:
        item = EmailDispatch(
            id=uuid4(),
            template_id=template_id,
            client_id=client_id,
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            message_id=message_id,
            retry_of_id=retry_of_id,
            retry_of_message_id=retry_of_message_id,
            status=status,
            detail=detail,
            attempted_at=datetime.now(UTC),
        )
        self.dispatches.append(item)
        return item

    async def update_dispatch_result(
        self,
        *,
        id: UUID,
        status: EmailDeliveryStatus,
        detail: str | None,
    ) -> EmailDispatch:
        current = next(item for item in self.dispatches if item.id == id)
        updated = replace(current, status=status, detail=detail)
        self.dispatches[self.dispatches.index(current)] = updated
        return updated

    async def reconcile_stale_pending_dispatches(
        self, *, template_id: UUID, client_ids: list[UUID]
    ) -> None:
        for index, item in enumerate(self.dispatches):
            if (
                item.template_id == template_id
                and item.client_id in client_ids
                and item.status is EmailDeliveryStatus.PENDING
            ):
                self.dispatches[index] = replace(
                    item,
                    status=EmailDeliveryStatus.UNKNOWN,
                    detail="sender_interrupted",
                )

    async def latest_delivery_barrier(
        self, *, template_id: UUID, client_id: UUID
    ) -> EmailDispatch | None:
        matches = [
            item
            for item in self.dispatches
            if item.template_id == template_id and item.client_id == client_id
        ]
        if not matches or matches[-1].status not in {
            EmailDeliveryStatus.PENDING,
            EmailDeliveryStatus.SENT,
            EmailDeliveryStatus.UNKNOWN,
        }:
            return None
        return matches[-1]


def _settings() -> EmailSenderSettings:
    return EmailSenderSettings(
        sender_name="Escritório Sintético",
        sender_email="contato@example.com",
        smtp_host="smtp.example.com",
        smtp_port=587,
        security=SmtpSecurity.STARTTLS,
        username="contato@example.com",
        max_recipients=50,
    )


def _template() -> MessageTemplate:
    now = datetime.now(UTC)
    return MessageTemplate(
        id=uuid4(),
        name="Pendência",
        subject="Pendência de {{nome}}",
        body="Olá, {{nome}}.",
        created_at=now,
        updated_at=now,
    )


def _client(email: str | None) -> ClientFolder:
    now = datetime.now(UTC)
    return ClientFolder(
        id=uuid4(),
        display_name="Cliente Sintético",
        email=email,
        profile_data={},
        created_at=now,
        updated_at=now,
    )


async def test_configure_sender_persists_only_public_settings_and_audits() -> None:
    repository = FakeCommunications(settings=None, template=None)
    audit = FakeAudit()
    transaction = FakeTransaction()

    saved = await ConfigureEmailSenderUseCase(
        repository=repository,  # type: ignore[arg-type]
        audit=RecordAuditEventUseCase(audit),
        transaction=transaction,
    ).execute(
        actor_user_id=uuid4(),
        sender_name=" Escritório   Sintético ",
        sender_email="CONTATO@example.com",
        smtp_host="SMTP.EXAMPLE.COM",
        smtp_port=587,
        security=SmtpSecurity.STARTTLS,
        username="contato@example.com",
        max_recipients=25,
    )

    assert saved.sender_name == "Escritório Sintético"
    assert saved.smtp_host == "smtp.example.com"
    assert transaction.commits == 1
    assert audit.events[0].context == {}


async def test_batch_sends_individually_and_records_missing_email() -> None:
    template = _template()
    with_email = _client("cliente@example.com")
    without_email = _client(None)
    repository = FakeCommunications(settings=_settings(), template=template)
    sender = FakeSender(EmailDeliveryResult(EmailDeliveryStatus.SENT))
    audit = FakeAudit()
    transaction = FakeTransaction()

    results = await SendEmailBatchUseCase(
        communications=repository,  # type: ignore[arg-type]
        clients=FakeClients(  # type: ignore[arg-type]
            {with_email.id: with_email, without_email.id: without_email}
        ),
        sender=sender,
        audit=RecordAuditEventUseCase(audit),
        transaction=transaction,
    ).execute(
        actor_user_id=uuid4(),
        template_id=template.id,
        client_ids=[with_email.id, without_email.id],
        credential="segredo-sintético",
        confirm_repeat=False,
    )

    assert [item.status for item in results] == [
        EmailDeliveryStatus.SENT,
        EmailDeliveryStatus.MISSING_EMAIL,
    ]
    assert [item.recipient for item in sender.messages] == ["cliente@example.com"]
    assert sender.messages[0].subject == "Pendência de Cliente Sintético"
    assert sender.credentials == ["segredo-sintético"]
    assert [event.context["phase"] for event in audit.events] == [
        "started",
        "completed",
    ]
    assert audit.events[-1].context["sent_count"] == "1"


@pytest.mark.parametrize(
    "previous_status",
    [
        EmailDeliveryStatus.PENDING,
        EmailDeliveryStatus.SENT,
        EmailDeliveryStatus.UNKNOWN,
    ],
)
async def test_batch_requires_confirmation_before_repeating_uncertain_delivery(
    previous_status: EmailDeliveryStatus,
) -> None:
    template = _template()
    client = _client("cliente@example.com")
    repository = FakeCommunications(settings=_settings(), template=template)
    await repository.create_dispatch(
        template_id=template.id,
        client_id=client.id,
        recipient_email=client.email,
        subject="anterior",
        body="anterior",
        message_id="<anterior@delta-force.local>",
        retry_of_id=None,
        retry_of_message_id=None,
        status=previous_status,
        detail=None,
    )
    sender = FakeSender(EmailDeliveryResult(EmailDeliveryStatus.SENT))

    expected_error = (
        DeliveryAlreadyConfirmedError
        if previous_status is EmailDeliveryStatus.SENT
        else RepeatConfirmationRequiredError
    )
    with pytest.raises(expected_error):
        await SendEmailBatchUseCase(
            communications=repository,  # type: ignore[arg-type]
            clients=FakeClients({client.id: client}),  # type: ignore[arg-type]
            sender=sender,
            audit=RecordAuditEventUseCase(FakeAudit()),
            transaction=FakeTransaction(),
        ).execute(
            actor_user_id=uuid4(),
            template_id=template.id,
            client_ids=[client.id],
            credential="segredo-sintético",
            confirm_repeat=False,
        )

    assert sender.messages == []
    assert len(repository.dispatches) == 1


def test_insecure_sender_settings_are_restricted_to_explicit_local_development() -> (
    None
):
    arguments = {
        "sender_name": "Escritório Sintético",
        "sender_email": "contato@example.com",
        "smtp_host": "localhost",
        "smtp_port": 1025,
        "security": SmtpSecurity.NONE_DEV,
        "username": None,
        "max_recipients": 50,
    }

    with pytest.raises(ValueError, match="local development"):
        normalize_sender_settings(**arguments)

    settings = normalize_sender_settings(
        **arguments,
        allow_insecure_local_smtp=True,
    )
    assert settings.security is SmtpSecurity.NONE_DEV


async def test_batch_validates_every_client_before_sending_any_message() -> None:
    template = _template()
    valid_client = _client("cliente@example.com")
    missing_client_id = uuid4()
    repository = FakeCommunications(settings=_settings(), template=template)
    sender = FakeSender(EmailDeliveryResult(EmailDeliveryStatus.SENT))
    clients = FakeClients({valid_client.id: valid_client})

    with pytest.raises(ValueError, match="one or more clients do not exist"):
        await SendEmailBatchUseCase(
            communications=repository,  # type: ignore[arg-type]
            clients=clients,  # type: ignore[arg-type]
            sender=sender,
            audit=RecordAuditEventUseCase(FakeAudit()),
            transaction=FakeTransaction(),
        ).execute(
            actor_user_id=uuid4(),
            template_id=template.id,
            client_ids=[valid_client.id, missing_client_id],
            credential="segredo-sintético",
            confirm_repeat=False,
        )

    assert sender.messages == []
    assert repository.dispatches == []


async def test_batch_checks_repeat_confirmation_before_sending_fresh_clients() -> None:
    template = _template()
    fresh_client = _client("novo@example.com")
    repeated_client = _client("anterior@example.com")
    repository = FakeCommunications(settings=_settings(), template=template)
    await repository.create_dispatch(
        template_id=template.id,
        client_id=repeated_client.id,
        recipient_email=repeated_client.email,
        subject="anterior",
        body="anterior",
        message_id="<anterior@delta-force.local>",
        retry_of_id=None,
        retry_of_message_id=None,
        status=EmailDeliveryStatus.UNKNOWN,
        detail="smtp_result_unknown",
    )
    sender = FakeSender(EmailDeliveryResult(EmailDeliveryStatus.SENT))

    with pytest.raises(RepeatConfirmationRequiredError):
        await SendEmailBatchUseCase(
            communications=repository,  # type: ignore[arg-type]
            clients=FakeClients(  # type: ignore[arg-type]
                {
                    fresh_client.id: fresh_client,
                    repeated_client.id: repeated_client,
                }
            ),
            sender=sender,
            audit=RecordAuditEventUseCase(FakeAudit()),
            transaction=FakeTransaction(),
        ).execute(
            actor_user_id=uuid4(),
            template_id=template.id,
            client_ids=[fresh_client.id, repeated_client.id],
            credential="segredo-sintético",
            confirm_repeat=False,
        )

    assert sender.messages == []
    assert len(repository.dispatches) == 1


async def test_smtp_adapter_never_allows_insecure_remote_delivery() -> None:
    result = await SmtpEmailSender(allow_insecure_local_smtp=True).send(
        settings=replace(
            _settings(), security=SmtpSecurity.NONE_DEV, smtp_host="smtp.example.com"
        ),
        message=OutboundEmail(
            message_id="<synthetic@delta-force.local>",
            recipient="cliente@example.com",
            subject="Assunto",
            body="Corpo",
        ),
        credential=None,
    )

    assert result.status is EmailDeliveryStatus.REJECTED
    assert result.detail == "insecure_smtp_not_allowed"


async def test_smtp_adapter_reports_authentication_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class AuthenticationRejectedSmtp:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def __enter__(self) -> "AuthenticationRejectedSmtp":
            return self

        def __exit__(self, *args: object) -> None:
            del args

        def ehlo(self) -> tuple[int, bytes]:
            return 250, b"ok"

        def starttls(self, *, context: object) -> None:
            del context

        def login(self, username: str, password: str) -> None:
            del username, password
            raise smtplib.SMTPAuthenticationError(535, b"synthetic rejection")

    monkeypatch.setattr(smtplib, "SMTP", AuthenticationRejectedSmtp)

    result = await SmtpEmailSender().send(
        settings=_settings(),
        message=OutboundEmail(
            message_id="<synthetic@delta-force.local>",
            recipient="cliente@example.com",
            subject="Assunto",
            body="Corpo",
        ),
        credential="segredo-sintético",
    )

    assert result.status is EmailDeliveryStatus.REJECTED
    assert result.detail == "smtp_authentication_failed"


async def test_confirmed_delivery_is_never_repeated_even_with_confirmation() -> None:
    template = _template()
    client = _client("cliente@example.com")
    repository = FakeCommunications(settings=_settings(), template=template)
    await repository.create_dispatch(
        template_id=template.id,
        client_id=client.id,
        recipient_email=client.email,
        subject="anterior",
        body="anterior",
        message_id="<confirmed@delta-force.local>",
        retry_of_id=None,
        retry_of_message_id=None,
        status=EmailDeliveryStatus.SENT,
        detail=None,
    )
    sender = FakeSender(EmailDeliveryResult(EmailDeliveryStatus.SENT))

    with pytest.raises(DeliveryAlreadyConfirmedError):
        await SendEmailBatchUseCase(
            communications=repository,  # type: ignore[arg-type]
            clients=FakeClients({client.id: client}),  # type: ignore[arg-type]
            sender=sender,
            audit=RecordAuditEventUseCase(FakeAudit()),
            transaction=FakeTransaction(),
        ).execute(
            actor_user_id=uuid4(),
            template_id=template.id,
            client_ids=[client.id],
            credential="segredo-sintético",
            confirm_repeat=True,
        )

    assert sender.messages == []


async def test_stale_pending_from_previous_runtime_is_retried_with_reference() -> None:
    template = _template()
    client = _client("cliente@example.com")
    repository = FakeCommunications(settings=_settings(), template=template)
    previous = await repository.create_dispatch(
        template_id=template.id,
        client_id=client.id,
        recipient_email=client.email,
        subject="anterior",
        body="anterior",
        message_id="<pending@delta-force.local>",
        retry_of_id=None,
        retry_of_message_id=None,
        status=EmailDeliveryStatus.PENDING,
        detail=None,
    )

    results = await SendEmailBatchUseCase(
        communications=repository,  # type: ignore[arg-type]
        clients=FakeClients({client.id: client}),  # type: ignore[arg-type]
        sender=FakeSender(EmailDeliveryResult(EmailDeliveryStatus.SENT)),
        audit=RecordAuditEventUseCase(FakeAudit()),
        transaction=FakeTransaction(),
    ).execute(
        actor_user_id=uuid4(),
        template_id=template.id,
        client_ids=[client.id],
        credential="segredo-sintético",
        confirm_repeat=True,
    )

    assert repository.dispatches[0].status is EmailDeliveryStatus.UNKNOWN
    assert repository.dispatches[0].detail == "sender_interrupted"
    assert results[0].status is EmailDeliveryStatus.SENT
    assert results[0].retry_of_id == previous.id
    assert results[0].retry_of_message_id == previous.message_id


async def test_latest_rejection_supersedes_older_unknown_attempt() -> None:
    template = _template()
    client = _client("cliente@example.com")
    repository = FakeCommunications(settings=_settings(), template=template)
    await repository.create_dispatch(
        template_id=template.id,
        client_id=client.id,
        recipient_email=client.email,
        subject="incerto",
        body="incerto",
        message_id="<unknown@delta-force.local>",
        retry_of_id=None,
        retry_of_message_id=None,
        status=EmailDeliveryStatus.UNKNOWN,
        detail="smtp_result_unknown",
    )
    await repository.create_dispatch(
        template_id=template.id,
        client_id=client.id,
        recipient_email=client.email,
        subject="rejeitado",
        body="rejeitado",
        message_id="<rejected@delta-force.local>",
        retry_of_id=None,
        retry_of_message_id=None,
        status=EmailDeliveryStatus.REJECTED,
        detail="smtp_rejected",
    )

    results = await SendEmailBatchUseCase(
        communications=repository,  # type: ignore[arg-type]
        clients=FakeClients({client.id: client}),  # type: ignore[arg-type]
        sender=FakeSender(EmailDeliveryResult(EmailDeliveryStatus.SENT)),
        audit=RecordAuditEventUseCase(FakeAudit()),
        transaction=FakeTransaction(),
    ).execute(
        actor_user_id=uuid4(),
        template_id=template.id,
        client_ids=[client.id],
        credential="segredo-sintético",
        confirm_repeat=False,
    )

    assert results[0].status is EmailDeliveryStatus.SENT
    assert results[0].retry_of_id is None
    assert results[0].retry_of_message_id is None


async def test_confirmed_unknown_retry_keeps_previous_attempt_reference() -> None:
    template = _template()
    client = _client("cliente@example.com")
    repository = FakeCommunications(settings=_settings(), template=template)
    previous = await repository.create_dispatch(
        template_id=template.id,
        client_id=client.id,
        recipient_email=client.email,
        subject="anterior",
        body="anterior",
        message_id="<unknown@delta-force.local>",
        retry_of_id=None,
        retry_of_message_id=None,
        status=EmailDeliveryStatus.UNKNOWN,
        detail="smtp_result_unknown",
    )

    results = await SendEmailBatchUseCase(
        communications=repository,  # type: ignore[arg-type]
        clients=FakeClients({client.id: client}),  # type: ignore[arg-type]
        sender=FakeSender(EmailDeliveryResult(EmailDeliveryStatus.SENT)),
        audit=RecordAuditEventUseCase(FakeAudit()),
        transaction=FakeTransaction(),
    ).execute(
        actor_user_id=uuid4(),
        template_id=template.id,
        client_ids=[client.id],
        credential="segredo-sintético",
        confirm_repeat=True,
    )

    assert results[0].retry_of_id == previous.id
    assert results[0].retry_of_message_id == previous.message_id


async def test_batch_audits_start_and_failure_after_partial_external_effect() -> None:
    template = _template()
    first = _client("primeiro@example.com")
    second = _client("segundo@example.com")
    repository = FakeCommunications(settings=_settings(), template=template)
    audit = FakeAudit()

    @dataclass
    class InterruptingSender:
        calls: int = 0

        async def send(
            self,
            *,
            settings: EmailSenderSettings,
            message: OutboundEmail,
            credential: str | None,
        ) -> EmailDeliveryResult:
            del settings, message, credential
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("synthetic interruption")
            return EmailDeliveryResult(EmailDeliveryStatus.SENT)

    with pytest.raises(RuntimeError, match="synthetic interruption"):
        await SendEmailBatchUseCase(
            communications=repository,  # type: ignore[arg-type]
            clients=FakeClients(  # type: ignore[arg-type]
                {first.id: first, second.id: second}
            ),
            sender=InterruptingSender(),  # type: ignore[arg-type]
            audit=RecordAuditEventUseCase(audit),
            transaction=FakeTransaction(),
        ).execute(
            actor_user_id=uuid4(),
            template_id=template.id,
            client_ids=[first.id, second.id],
            credential="segredo-sintético",
            confirm_repeat=False,
        )

    assert [event.context["phase"] for event in audit.events] == [
        "started",
        "failed",
    ]
    assert audit.events[-1].result is AuditResult.FAILURE
    assert audit.events[-1].context["sent_count"] == "1"
    assert audit.events[-1].context["unknown_count"] == "1"


@pytest.mark.parametrize(
    "failure",
    [
        ConnectionRefusedError("synthetic refusal"),
        OSError("synthetic DNS failure"),
        ssl.SSLCertVerificationError("synthetic certificate failure"),
    ],
)
async def test_smtp_transport_failures_before_data_are_definitive(
    monkeypatch: pytest.MonkeyPatch, failure: OSError
) -> None:
    def fail_before_connection(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise failure

    monkeypatch.setattr(smtplib, "SMTP", fail_before_connection)
    result = await SmtpEmailSender().send(
        settings=_settings(),
        message=OutboundEmail(
            message_id="<synthetic@delta-force.local>",
            recipient="cliente@example.com",
            subject="Assunto",
            body="Corpo",
        ),
        credential="segredo-sintético",
    )

    assert result.status is EmailDeliveryStatus.REJECTED
    assert result.detail == "smtp_failed_before_data"


async def test_smtp_starttls_failure_before_data_is_definitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StartTlsFailure:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def ehlo(self) -> tuple[int, bytes]:
            return 250, b"ok"

        def starttls(self, *, context: object) -> None:
            del context
            raise smtplib.SMTPNotSupportedError("synthetic STARTTLS failure")

        def close(self) -> None:
            return None

    monkeypatch.setattr(smtplib, "SMTP", StartTlsFailure)
    result = await SmtpEmailSender().send(
        settings=_settings(),
        message=OutboundEmail(
            message_id="<synthetic@delta-force.local>",
            recipient="cliente@example.com",
            subject="Assunto",
            body="Corpo",
        ),
        credential="segredo-sintético",
    )

    assert result.status is EmailDeliveryStatus.REJECTED
    assert result.detail == "smtp_failed_before_data"


async def test_smtp_disconnect_during_data_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DataDisconnect:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def ehlo(self) -> tuple[int, bytes]:
            return 250, b"ok"

        def starttls(self, *, context: object) -> None:
            del context

        def login(self, username: str, password: str) -> None:
            del username, password

        def mail(self, sender: str) -> tuple[int, bytes]:
            del sender
            return 250, b"ok"

        def rcpt(self, recipient: str) -> tuple[int, bytes]:
            del recipient
            return 250, b"ok"

        def docmd(self, command: str) -> tuple[int, bytes]:
            assert command == "DATA"
            return 354, b"continue"

        def send(self, payload: bytes) -> None:
            del payload
            raise smtplib.SMTPServerDisconnected("synthetic disconnect")

        def getreply(self) -> tuple[int, bytes]:
            raise AssertionError("reply is unavailable after disconnect")

        def close(self) -> None:
            return None

    monkeypatch.setattr(smtplib, "SMTP", DataDisconnect)
    result = await SmtpEmailSender().send(
        settings=_settings(),
        message=OutboundEmail(
            message_id="<synthetic@delta-force.local>",
            recipient="cliente@example.com",
            subject="Assunto",
            body="Corpo",
        ),
        credential="segredo-sintético",
    )

    assert result.status is EmailDeliveryStatus.UNKNOWN
    assert result.detail == "smtp_result_unknown_after_data"
