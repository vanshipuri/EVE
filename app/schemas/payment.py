from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.payment import PaymentStatus


class PaymentCreate(BaseModel):
    booking_id: int
    payment_method: Optional[Literal["card", "upi", "netbanking", "wallet"]] = "upi"
    # Test hook for the MOCK gateway: force a failure to exercise FAILED flows.
    simulate_failure: bool = False


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int
    amount: Decimal
    currency: str
    status: PaymentStatus
    payment_method: Optional[str] = None
    provider_payment_id: Optional[str] = None
    failure_reason: Optional[str] = None
    created_at: datetime


class WebhookPayload(BaseModel):
    """Simulated provider callback. event_id is the idempotency key."""

    event_id: str = Field(min_length=1, max_length=128)
    booking_id: int
    status: Literal["SUCCESS", "FAILED"]
    provider_payment_id: Optional[str] = Field(default=None, max_length=128)
    failure_reason: Optional[str] = Field(default=None, max_length=500)


class WebhookResponse(BaseModel):
    received: bool = True
    deduped: bool = False
    booking_id: int
    booking_status: Optional[str] = None
    payment_id: Optional[int] = None
    message: str
