from pydantic import BaseModel, ConfigDict, Field


class DiagnosticTestCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Z0-9_\-]+$")
    description: str | None = None
    category: str | None = Field(default=None, max_length=128)


class DiagnosticTestUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=128)


class DiagnosticTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: str | None = None
    category: str | None = None
