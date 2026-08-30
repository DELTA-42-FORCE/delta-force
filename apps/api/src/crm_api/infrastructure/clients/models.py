"""Modelos SQLAlchemy da pasta digital flexível de clientes."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from crm_api.infrastructure.database import Base


class ClientFolderModel(Base):
    """Metadados persistentes da pasta de um cliente; documentos ficam fora do DB."""

    __tablename__ = "client_folders"
    __table_args__ = (
        CheckConstraint(
            "length(trim(display_name)) > 0",
            name="ck_client_folders_display_name_not_blank",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    display_name: Mapped[str] = mapped_column(String(), nullable=False)
    profile_data: Mapped[dict[str, str]] = mapped_column(
        JSON(), nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
