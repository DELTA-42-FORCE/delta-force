"""Modelo SQLAlchemy dos metadados de documento; o binário fica no filesystem."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from crm_api.infrastructure.database import Base

ACCEPTED_MEDIA_TYPES = ("application/pdf", "image/jpeg")


class DocumentModel(Base):
    """Aponta para o arquivo na área privada sem armazenar o conteúdo."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "media_type IN ('application/pdf', 'image/jpeg')",
            name="ck_documents_media_type",
        ),
        CheckConstraint("byte_size > 0", name="ck_documents_byte_size_positive"),
        CheckConstraint(
            "length(checksum_sha256) = 64",
            name="ck_documents_checksum_length",
        ),
        CheckConstraint(
            "length(trim(original_filename)) > 0",
            name="ck_documents_original_filename_not_blank",
        ),
        CheckConstraint(
            "status IN ('pending', 'received_regular', 'incorrect_incomplete')",
            name="ck_documents_status",
        ),
        UniqueConstraint("storage_key", name="uq_documents_storage_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_folder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("client_folders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(), nullable=False)
    # Anotações livres do proprietário: nenhuma é obrigatória (#22).
    title: Mapped[str | None] = mapped_column(String(), nullable=True)
    category: Mapped[str | None] = mapped_column(String(), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(), nullable=True)
    status: Mapped[str] = mapped_column(
        String(), nullable=False, server_default="pending", index=True
    )
    storage_key: Mapped[str] = mapped_column(String(), nullable=False)
    media_type: Mapped[str] = mapped_column(String(), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    stored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
