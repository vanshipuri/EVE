"""Deduplication ledger for payment webhooks.

The PK on event_id is the idempotency guarantee: the database rejects
a second insert of the same event even under concurrent retries.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"), nullable=True)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    result: Mapped[str] = mapped_column(String(32), default="processed", nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
