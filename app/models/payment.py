import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=PaymentStatus.PENDING.value, nullable=False, index=True)

    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    # Event that created this payment (webhook idempotency). Unique when present.
    provider_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True, index=True)
    # Client idempotency key (Idempotency-Key header on POST /payments).
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    booking: Mapped["Booking"] = relationship("Booking", back_populates="payments")
