import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.centre import Centre
    from app.models.diagnostic_test import DiagnosticTest
    from app.models.payment import Payment
    from app.models.user import User


class BookingStatus(enum.StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"), nullable=False, index=True)
    test_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostic_tests.id"), nullable=False, index=True
    )

    appointment_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    # Snapshot of price at booking time so later price changes don't rewrite history.
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)

    # Stored as plain string for SQLite/Postgres portability; validated via BookingStatus enum.
    status: Mapped[str] = mapped_column(
        String(20), default=BookingStatus.PENDING.value, nullable=False, index=True
    )

    # Optional client idempotency key (Idempotency-Key header). Unique per user.
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="bookings")
    centre: Mapped["Centre"] = relationship("Centre", back_populates="bookings")
    test: Mapped["DiagnosticTest"] = relationship("DiagnosticTest")
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="booking", cascade="all, delete-orphan"
    )
