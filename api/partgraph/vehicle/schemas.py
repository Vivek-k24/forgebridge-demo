from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VehicleConfigurationInput(BaseModel):
    year: int = Field(ge=1886, le=2100)
    market: str = Field(min_length=1, max_length=32)
    make: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=96)
    generation: str | None = Field(default=None, max_length=96)
    trim: str | None = Field(default=None, max_length=128)
    body_style: str | None = Field(default=None, max_length=64)
    engine: str | None = Field(default=None, max_length=128)
    transmission: str | None = Field(default=None, max_length=128)
    drivetrain: str | None = Field(default=None, max_length=64)

    @field_validator("market", "make", "model")
    @classmethod
    def clean_required(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("value cannot be blank")
        return cleaned

    @field_validator(
        "generation",
        "trim",
        "body_style",
        "engine",
        "transmission",
        "drivetrain",
    )
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


class VehicleConfigurationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    year: int
    market: str
    make: str
    model: str
    generation: str | None
    trim: str | None
    body_style: str | None
    engine: str | None
    transmission: str | None
    drivetrain: str | None
    identity_source: str
    verification_status: str
    created_at: datetime


class VehicleConfigurationResult(BaseModel):
    created: bool
    resolution: Literal["created", "matched", "enriched"]
    configuration: VehicleConfigurationRead
