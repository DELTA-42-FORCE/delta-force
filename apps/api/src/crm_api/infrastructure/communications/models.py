"""Modelo SQLAlchemy dos modelos de mensagem."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text, Uuid, func
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
