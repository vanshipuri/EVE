from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.payment import PaymentStatus


class PaymentCreate(BaseModel):
    booking_id: int
    payment_method: Literal["card", "upi", "netbanking", "wallet"] | None = "upi"
    # Test hook for the MOCK gateway: force a failure to exercise FAILED flows.
    simulate_failure: bool = False


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int
    amount: Decimal
    currency: str
    status: PaymentStatus
    payment_method: str | None = None
    provider_payment_id: str | None = None
    failure_reason: str | None = None
    created_at: datetime


class WebhookPayload(BaseModel):
    """Simulated provider callback. event_id is the idempotency key."""

    event_id: str = Field(min_length=1, max_length=128)
    booking_id: int
    status: Literal["SUCCESS", "FAILED"]
    provider_payment_id: str | None = Field(default=None, max_length=128)
    failure_reason: str | None = Field(default=None, max_length=500)


class WebhookResponse(BaseModel):
    received: bool = True
    deduped: bool = False
    booking_id: int
    booking_status: str | None = None
    payment_id: int | None = None
    message: str
