from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from ..vehicle.schemas import VehicleConfigurationRead, VehicleSelectionInput


class VehicleIdentitySnapshot(BaseModel):
    year: int
    market: str
    make: str
    model: str
    generation: str | None = None
    trim: str | None = None
    body_style: str | None = None
    engine: str | None = None
    transmission: str | None = None
    drivetrain: str | None = None


class ManualUserVehicleCreate(BaseModel):
    nickname: str | None = Field(default=None, max_length=80)
    selection: VehicleSelectionInput

    @field_validator("nickname")
    @classmethod
    def clean_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @field_validator("selection")
    @classmethod
    def require_trim(cls, value: VehicleSelectionInput) -> VehicleSelectionInput:
        if value.trim is None or not value.trim.strip():
            raise ValueError("trim is required for manual garage vehicles")
        return value


class VinRequest(BaseModel):
    market: str = Field(min_length=1, max_length=64)
    vin: str = Field(min_length=1, max_length=64)


class VinUserVehicleCreate(VinRequest):
    nickname: str | None = Field(default=None, max_length=80)

    @field_validator("nickname")
    @classmethod
    def clean_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


class VinDecodeRead(BaseModel):
    source: Literal["provider", "cache"]
    provider: str
    masked_vin: str
    observed_at: datetime
    expires_at: datetime
    resolution: Literal["matched", "ambiguous", "manual_candidate"]
    identity: VehicleIdentitySnapshot
    matches: list[VehicleConfigurationRead]


class UserVehicleRead(BaseModel):
    id: UUID
    nickname: str | None
    canonical_configuration_id: UUID | None
    identity_source: Literal["manual", "vin"]
    identity_resolution: Literal["matched", "ambiguous", "manual_candidate"]
    identity: VehicleIdentitySnapshot
    masked_vin: str | None
    decoder_provider: str | None
    decoder_observed_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
