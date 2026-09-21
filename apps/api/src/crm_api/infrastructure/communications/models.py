"""Modelo SQLAlchemy dos modelos de mensagem."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from crm_api.infrastructure.database import Base


class MessageTemplateModel(Base):
    __tablename__ = "message_templates"
    __table_args__ = (
        CheckConstraint(
            "length(trim(name)) BETWEEN 1 AND 120",
            name="ck_message_templates_name_length",
        ),
        CheckConstraint(
            "length(trim(subject)) BETWEEN 1 AND 200",
            name="ck_message_templates_subject_length",
        ),
        CheckConstraint(
            "length(trim(body)) BETWEEN 1 AND 20000",
            name="ck_message_templates_body_length",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class EmailSenderSettingsModel(Base):
    __tablename__ = "email_sender_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_email_sender_settings_singleton"),
        CheckConstraint(
            "security IN ('starttls', 'tls', 'none_dev')",
            name="ck_email_sender_settings_security",
        ),
        CheckConstraint(
            "smtp_port BETWEEN 1 AND 65535",
            name="ck_email_sender_settings_port",
        ),
        CheckConstraint(
            "max_recipients BETWEEN 1 AND 100",
            name="ck_email_sender_settings_max_recipients",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    sender_name: Mapped[str] = mapped_column(String(120), nullable=False)
    sender_email: Mapped[str] = mapped_column(String(320), nullable=False)
    smtp_host: Mapped[str] = mapped_column(String(253), nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False)
    security: Mapped[str] = mapped_column(String(16), nullable=False)
    username: Mapped[str | None] = mapped_column(String(320), nullable=True)
    max_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=50)


class EmailDispatchModel(Base):
    __tablename__ = "email_dispatches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'sent', 'rejected', 'unknown', "
            "'skipped_duplicate', 'missing_email')",
            name="ck_email_dispatches_status",
        ),
        CheckConstraint(
            "(retry_of_id IS NULL AND retry_of_message_id IS NULL) OR "
            "(retry_of_id IS NOT NULL AND retry_of_message_id IS NOT NULL)",
            name="ck_email_dispatches_retry_reference",
        ),
        Index("ix_email_dispatches_retry_of_id", "retry_of_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("client_folders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    recipient_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text(), nullable=False)
    message_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    retry_of_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("email_dispatches.id", ondelete="RESTRICT"),
        nullable=True,
    )
    retry_of_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(200), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
