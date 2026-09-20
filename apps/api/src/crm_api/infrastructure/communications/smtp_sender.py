"""Adaptador SMTP seguro; credenciais existem somente durante o envio."""

import asyncio
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
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
            and settings.smtp_host.lower() in _LOOPBACK_HOSTS
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

        try:
            context = ssl.create_default_context()
            if settings.security is SmtpSecurity.TLS:
                with smtplib.SMTP_SSL(
                    settings.smtp_host,
                    settings.smtp_port,
                    timeout=self.timeout_seconds,
                    context=context,
                ) as client:
                    self._authenticate_and_send(client, settings, credential, payload)
            else:
                with smtplib.SMTP(
                    settings.smtp_host,
                    settings.smtp_port,
                    timeout=self.timeout_seconds,
                ) as client:
                    client.ehlo()
                    if settings.security is SmtpSecurity.STARTTLS:
                        client.starttls(context=context)
                        client.ehlo()
                    self._authenticate_and_send(client, settings, credential, payload)
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
            # A conexão pode cair depois de DATA: o servidor talvez já tenha
            # aceitado a mensagem. Não classificar como falha reenviável evita
            # duplicidade automática.
            return EmailDeliveryResult(
                status=EmailDeliveryStatus.UNKNOWN,
                detail="smtp_result_unknown",
            )
        return EmailDeliveryResult(status=EmailDeliveryStatus.SENT)

    @staticmethod
    def _authenticate_and_send(
        client: smtplib.SMTP,
        settings: EmailSenderSettings,
        credential: str | None,
        payload: EmailMessage,
    ) -> None:
        if settings.username:
            client.login(settings.username, credential or "")
        refused = client.send_message(payload)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
