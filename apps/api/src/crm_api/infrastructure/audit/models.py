"""Modelos SQLAlchemy da trilha de auditoria."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from crm_api.infrastructure.database import Base


class AuditEventModel(Base):
    """Registro persistente e append-only de uma ação relevante."""

    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            "actor_kind IN ('authenticated', 'anonymous')",
            name="ck_audit_events_actor_kind",
        ),
        CheckConstraint(
            "result IN ('success', 'denied', 'failure')",
            name="ck_audit_events_result",
        ),
        CheckConstraint(
            "action IN ('auth.owner_setup', 'auth.login', "
            "'auth.owner_profile_view', 'auth.logout', "
            "'auth.access_denied', 'audit.log_view', "
            "'client_folder.created', 'client_folder.viewed', "
            "'client_folder.updated', 'document.stored')",
            name="ck_audit_events_action",
        ),
        CheckConstraint(
            "resource_type IN ('owner_account', 'session', 'route', "
            "'audit_log', 'client_folder', 'document')",
            name="ck_audit_events_resource_type",
        ),
        CheckConstraint(
            "(actor_kind = 'authenticated' AND actor_user_id IS NOT NULL) OR "
            "(actor_kind = 'anonymous' AND actor_user_id IS NULL)",
            name="ck_audit_events_actor_identity",
        ),
        Index("ix_audit_events_actor_user_id", "actor_user_id"),
        Index("ix_audit_events_occurred_at_id", "occurred_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actor_kind: Mapped[str] = mapped_column(String(), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(), nullable=True)
    result: Mapped[str] = mapped_column(String(), nullable=False)
    context: Mapped[dict[str, str]] = mapped_column(JSON(), nullable=False)
