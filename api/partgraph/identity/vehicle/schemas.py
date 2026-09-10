from datetime import datetime
from math import isfinite
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .policy import validate_supported_year

ConfigurationQualifierValue = str | int | float | bool


def _clean_configuration_qualifiers(
    value: dict[str, ConfigurationQualifierValue],
) -> dict[str, ConfigurationQualifierValue]:
    cleaned: dict[str, ConfigurationQualifierValue] = {}
    for raw_key, raw_value in value.items():
        key = "_".join(raw_key.strip().casefold().replace("-", " ").split())
        if not key or len(key) > 64:
            raise ValueError("configuration qualifier keys must be 1-64 characters")
        if isinstance(raw_value, str):
            normalized_value = " ".join(raw_value.split())
            if not normalized_value or len(normalized_value) > 128:
                raise ValueError(
                    "configuration qualifier string values must be 1-128 characters"
                )
            cleaned[key] = normalized_value
        elif isinstance(raw_value, bool):
            cleaned[key] = raw_value
        elif isinstance(raw_value, int):
            cleaned[key] = raw_value
        elif isinstance(raw_value, float) and isfinite(raw_value):
            cleaned[key] = raw_value
        else:
            raise ValueError("configuration qualifier values must be finite scalar values")
    return dict(sorted(cleaned.items()))


class VehicleConfigurationInput(BaseModel):
    year: int = Field(strict=True)
    market: str = Field(min_length=1, max_length=64)
    make: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=96)
    generation: str | None = Field(default=None, max_length=96)
    trim: str | None = Field(default=None, max_length=128)
    body_style: str | None = Field(default=None, max_length=64)
    engine: str | None = Field(default=None, max_length=128)
    transmission: str | None = Field(default=None, max_length=128)
    drivetrain: str | None = Field(default=None, max_length=64)
    configuration_qualifiers: dict[str, ConfigurationQualifierValue] = Field(
        default_factory=dict
    )

    @field_validator("year")
    @classmethod
    def enforce_supported_year(cls, value: int) -> int:
        return validate_supported_year(value)

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

    @field_validator("configuration_qualifiers")
    @classmethod
    def clean_configuration_qualifiers(
        cls,
        value: dict[str, ConfigurationQualifierValue],
    ) -> dict[str, ConfigurationQualifierValue]:
        return _clean_configuration_qualifiers(value)


class VehicleSelectionInput(BaseModel):
    year: int = Field(strict=True)
    market: str = Field(min_length=1, max_length=64)
    make: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=96)
    trim: str | None = Field(default=None, max_length=128)
    generation: str | None = Field(default=None, max_length=96)
    body_style: str | None = Field(default=None, max_length=64)
    engine: str | None = Field(default=None, max_length=128)
    transmission: str | None = Field(default=None, max_length=128)
    drivetrain: str | None = Field(default=None, max_length=64)
    configuration_qualifiers: dict[str, ConfigurationQualifierValue] = Field(
        default_factory=dict
    )

    @field_validator("year")
    @classmethod
    def enforce_supported_year(cls, value: int) -> int:
        return validate_supported_year(value)

    @field_validator("market", "make", "model")
    @classmethod
    def clean_required(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("value cannot be blank")
        return cleaned

    @field_validator(
        "trim",
        "generation",
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

    @field_validator("configuration_qualifiers")
    @classmethod
    def clean_configuration_qualifiers(
        cls,
        value: dict[str, ConfigurationQualifierValue],
    ) -> dict[str, ConfigurationQualifierValue]:
        return _clean_configuration_qualifiers(value)


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
    configuration_qualifiers: dict[str, ConfigurationQualifierValue]
    identity_source: str
    verification_status: str
    canonicalization_version: int
    created_at: datetime
    updated_at: datetime


class VehicleConfigurationResult(BaseModel):
    resolution: Literal["created", "matched", "enriched"]
    configuration: VehicleConfigurationRead


class VehicleSpecificationProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vehicle_configuration_id: UUID
    profile_version: int
    verification_status: str
    source_match_count: int
    profile: dict[str, object]
    source_matrix: dict[str, object]
    created_at: datetime
    updated_at: datetime


class VehicleSelectionNormalized(BaseModel):
    year: int
    market: str
    make: str
    model: str
    trim: str | None
    generation: str | None
    body_style: str | None = None
    engine: str | None = None
    transmission: str | None = None
    drivetrain: str | None = None
    configuration_qualifiers: dict[str, ConfigurationQualifierValue] = Field(
        default_factory=dict
    )


class VehicleSelectionResult(BaseModel):
    resolution: Literal["matched", "ambiguous", "manual_candidate"]
    normalized: VehicleSelectionNormalized
    matches: list[VehicleConfigurationRead]


class VehicleBrandRead(BaseModel):
    name: str
    status: Literal["active", "legacy"]
