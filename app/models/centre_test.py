"""Association: which test a centre offers, at what price."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.centre import Centre
    from app.models.diagnostic_test import DiagnosticTest


class CentreTest(Base):
    __tablename__ = "centre_tests"
    __table_args__ = (UniqueConstraint("centre_id", "test_id", name="uq_centre_test"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    centre_id: Mapped[int] = mapped_column(
        ForeignKey("centres.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostic_tests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    centre: Mapped["Centre"] = relationship("Centre", back_populates="centre_tests")
    test: Mapped["DiagnosticTest"] = relationship("DiagnosticTest", back_populates="centre_tests")
