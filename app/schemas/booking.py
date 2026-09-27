from datetime import UTC, datetime
from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    centre_id: int
    test_id: int
    appointment_time: datetime

    @field_validator("appointment_time")
    @classmethod
    def must_be_future(cls, v: datetime) -> datetime:
        # Normalize naive datetimes to UTC so aware/naive inputs compare correctly.
        value = v if v.tzinfo else v.replace(tzinfo=UTC)
        if value <= datetime.now(UTC):
            raise ValueError("appointment_time must be in the future")
        return v


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    centre_id: int
    test_id: int
    centre_name: str | None = None
    test_name: str | None = None
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
