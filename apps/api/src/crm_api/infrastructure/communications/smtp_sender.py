"""Adaptador SMTP seguro; credenciais existem somente durante o envio."""

import asyncio
from dataclasses import dataclass
from email.message import EmailMessage
from email.policy import SMTP as SMTP_POLICY
from email.utils import formataddr
from ipaddress import ip_address
import smtplib
import socket
import ssl

from crm_api.domain.communications.entities import (
    EmailDeliveryResult,
    EmailDeliveryStatus,
    EmailSenderSettings,
    OutboundEmail,
    SmtpSecurity,
)

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _resolves_only_to_loopback(host: str, port: int) -> bool:
    if host.lower() not in _LOOPBACK_HOSTS:
        return False
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        return False
    return bool(addresses) and all(
        ip_address(address[4][0]).is_loopback for address in addresses
    )


@dataclass(frozen=True, slots=True)
class SmtpEmailSender:
    allow_insecure_local_smtp: bool = False
    timeout_seconds: float = 20.0

    async def send(
        self,
        *,
        settings: EmailSenderSettings,
        message: OutboundEmail,
        credential: str | None,
    ) -> EmailDeliveryResult:
        return await asyncio.to_thread(
            self._send_sync,
            settings,
            message,
            credential,
        )

    def _send_sync(
        self,
        settings: EmailSenderSettings,
        message: OutboundEmail,
        credential: str | None,
    ) -> EmailDeliveryResult:
        if settings.security is SmtpSecurity.NONE_DEV and not (
            self.allow_insecure_local_smtp
            and _resolves_only_to_loopback(
                settings.smtp_host,
                settings.smtp_port,
            )
        ):
            return EmailDeliveryResult(
                status=EmailDeliveryStatus.REJECTED,
                detail="insecure_smtp_not_allowed",
            )
        if settings.username and not credential:
            return EmailDeliveryResult(
                status=EmailDeliveryStatus.REJECTED,
                detail="credential_required",
            )

        payload = EmailMessage()
        payload["From"] = formataddr((settings.sender_name, settings.sender_email))
        payload["To"] = message.recipient
        payload["Subject"] = message.subject
        payload["Message-ID"] = message.message_id
        payload.set_content(message.body)

        client: smtplib.SMTP | smtplib.SMTP_SSL | None = None
        acceptance_possible = False
        try:
            context = ssl.create_default_context()
            if settings.security is SmtpSecurity.TLS:
                client = smtplib.SMTP_SSL(
                    settings.smtp_host,
                    settings.smtp_port,
                    timeout=self.timeout_seconds,
                    context=context,
                )
            else:
                client = smtplib.SMTP(
                    settings.smtp_host,
                    settings.smtp_port,
                    timeout=self.timeout_seconds,
                )
                client.ehlo()
                if settings.security is SmtpSecurity.STARTTLS:
                    client.starttls(context=context)
                    client.ehlo()
            if settings.username:
                client.login(settings.username, credential or "")
            code, response = client.mail(settings.sender_email)
            if code != 250:
                raise smtplib.SMTPSenderRefused(code, response, settings.sender_email)
            code, response = client.rcpt(message.recipient)
            if code not in {250, 251}:
                raise smtplib.SMTPRecipientsRefused(
                    {message.recipient: (code, response)}
                )
            acceptance_possible = True
            client.data(payload.as_bytes(policy=SMTP_POLICY))
        except smtplib.SMTPAuthenticationError:
            return EmailDeliveryResult(
                status=EmailDeliveryStatus.REJECTED,
                detail="smtp_authentication_failed",
            )
        except (
            smtplib.SMTPRecipientsRefused,
            smtplib.SMTPSenderRefused,
            smtplib.SMTPDataError,
        ):
            return EmailDeliveryResult(
                status=EmailDeliveryStatus.REJECTED,
                detail="smtp_rejected",
            )
        except (smtplib.SMTPException, OSError, socket.timeout):
            return EmailDeliveryResult(
                status=(
                    EmailDeliveryStatus.UNKNOWN
                    if acceptance_possible
                    else EmailDeliveryStatus.REJECTED
                ),
                detail=(
                    "smtp_result_unknown"
                    if acceptance_possible
                    else "smtp_pre_data_failure"
                ),
            )
        finally:
            if client is not None:
                try:
                    close = getattr(client, "close", None)
                    if close is not None:
                        close()
                except (OSError, smtplib.SMTPException):
                    pass
        return EmailDeliveryResult(status=EmailDeliveryStatus.SENT)
