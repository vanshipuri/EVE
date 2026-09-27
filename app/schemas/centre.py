from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CentreCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    location: str = Field(min_length=2, max_length=500)
    phone: str | None = Field(default=None, max_length=32)


class CentreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    location: str | None = Field(default=None, min_length=2, max_length=500)
    phone: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None


class DiagnosticTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: str | None = None
    category: str | None = None


class CentreTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    price: Decimal
    currency: str
    is_available: bool
    test: DiagnosticTestOut


class CentreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str
    phone: str | None = None
    is_active: bool
    created_at: datetime


class CentreDetailOut(CentreOut):
    tests: list[CentreTestOut] = []


class CentreTestCreate(BaseModel):
    test_id: int
    price: Decimal = Field(gt=0, le=1000000)
    currency: str = Field(default="INR", max_length=8)
    is_available: bool = True


class CentreTestUpdate(BaseModel):
    price: Decimal | None = Field(default=None, gt=0, le=1000000)
    is_available: bool | None = None
