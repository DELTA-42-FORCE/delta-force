"""Modelos persistentes de contratos e parcelas."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from crm_api.domain.contracts.entities import FIXED_DEPOSIT_CENTS, MAX_INSTALLMENTS
from crm_api.infrastructure.database import Base


class ContractModel(Base):
    __tablename__ = "contracts"
    __table_args__ = (
        CheckConstraint(
            f"total_amount_cents > {FIXED_DEPOSIT_CENTS}",
            name="ck_contracts_total_exceeds_deposit",
        ),
        CheckConstraint(
            f"deposit_amount_cents = {FIXED_DEPOSIT_CENTS}",
            name="ck_contracts_fixed_deposit",
        ),
        CheckConstraint(
            "balance_amount_cents = total_amount_cents - deposit_amount_cents",
            name="ck_contracts_balance_consistent",
        ),
        CheckConstraint(
            f"installment_count BETWEEN 1 AND {MAX_INSTALLMENTS}",
            name="ck_contracts_installment_count",
        ),
        CheckConstraint(
            "status IN ('active', 'paid', 'cancelled')",
            name="ck_contracts_status",
        ),
        CheckConstraint(
            "(status = 'cancelled' AND cancelled_at IS NOT NULL) OR "
            "(status <> 'cancelled' AND cancelled_at IS NULL)",
            name="ck_contracts_cancellation_consistent",
        ),
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
    total_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deposit_amount_cents: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=FIXED_DEPOSIT_CENTS
    )
    balance_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    installment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    signal_paid_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    installments: Mapped[list["ContractInstallmentModel"]] = relationship(
        back_populates="contract",
        cascade="all, delete-orphan",
        order_by="ContractInstallmentModel.number",
        lazy="selectin",
    )


class ContractInstallmentModel(Base):
    __tablename__ = "contract_installments"
    __table_args__ = (
        UniqueConstraint(
            "contract_id", "number", name="uq_contract_installments_contract_number"
        ),
        CheckConstraint("number >= 1", name="ck_contract_installments_number"),
        CheckConstraint(
            "amount_cents >= 1", name="ck_contract_installments_amount_positive"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    contract: Mapped[ContractModel] = relationship(back_populates="installments")
