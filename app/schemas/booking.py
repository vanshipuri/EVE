from datetime import datetime
from decimal import Decimal
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    centre_id: int
    test_id: int
    appointment_time: datetime

    @field_validator("appointment_time")
    @classmethod
    def must_be_future(cls, v: datetime) -> datetime:
        # Compare against UTC; accept naive datetimes as UTC for simplicity.
        now = datetime.utcnow()
        value = v.replace(tzinfo=None) if v.tzinfo else v
        if value <= now:
            raise ValueError("appointment_time must be in the future")
        return v


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    centre_id: int
    test_id: int
    centre_name: Optional[str] = None
    test_name: Optional[str] = None
    appointment_time: datetime
    amount: Decimal
    currency: str
    status: BookingStatus
    created_at: datetime
    updated_at: datetime


T = TypeVar("T")


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class PaginationParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
