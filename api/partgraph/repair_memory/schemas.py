from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

FastenerKind = Literal["fastener", "small_part"]
FastenerState = Literal["installed", "removed", "stored", "missing", "damaged", "replaced"]
ProcurementState = Literal["needed", "ordered", "available", "unavailable"]
ObservationCategory = Literal[
    "general",
    "condition",
    "damage",
    "part_number",
    "before",
    "after",
    "removed_part",
    "current_step",
]
PhotoPurpose = Literal[
    "current_step",
    "removed_part",
    "fastener",
    "damage",
    "part_number",
    "before",
    "after",
    "general",
]


def _clean_required(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError("value must not be blank")
    return cleaned


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


class StorageLocationCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        return _clean_required(value)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class StorageLocationRead(BaseModel):
    id: UUID
    session_id: UUID
    label: str
    notes: str | None
    created_at: datetime


class FastenerCreate(BaseModel):
    kind: FastenerKind = "fastener"
    label: str = Field(min_length=1, max_length=120)
    origin: str | None = Field(default=None, max_length=160)
    position: str | None = Field(default=None, max_length=160)
    physical_state: FastenerState = "installed"
    storage_location_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        return _clean_required(value)

    @field_validator("origin", "position", "notes")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @model_validator(mode="after")
    def storage_matches_state(self) -> FastenerCreate:
        if self.physical_state == "stored" and self.storage_location_id is None:
            raise ValueError("stored fasteners require a storage_location_id")
        if self.physical_state in {"installed", "replaced"} and self.storage_location_id is not None:
            raise ValueError("installed or replaced fasteners cannot have a storage location")
        return self


class FastenerStateUpdate(BaseModel):
    physical_state: FastenerState
    storage_location_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @model_validator(mode="after")
    def storage_matches_state(self) -> FastenerStateUpdate:
        if self.physical_state == "stored" and self.storage_location_id is None:
            raise ValueError("stored fasteners require a storage_location_id")
        if self.physical_state in {"installed", "replaced"} and self.storage_location_id is not None:
            raise ValueError("installed or replaced fasteners cannot have a storage location")
        return self


class FastenerRead(BaseModel):
    id: UUID
    session_id: UUID
    kind: FastenerKind
    label: str
    origin: str | None
    position: str | None
    physical_state: FastenerState
    storage_location_id: UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class InventoryItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    quantity: int = Field(default=1, ge=1, le=9999)
    procurement_state: ProcurementState = "needed"
    reference: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _clean_required(value)

    @field_validator("reference", "notes")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class InventoryStateUpdate(BaseModel):
    procurement_state: ProcurementState
    quantity: int | None = Field(default=None, ge=1, le=9999)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class InventoryItemRead(BaseModel):
    id: UUID
    session_id: UUID
    name: str
    quantity: int
    procurement_state: ProcurementState
    reference: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ObservationCreate(BaseModel):
    category: ObservationCategory = "general"
    text: str = Field(min_length=1, max_length=1000)
    fastener_id: UUID | None = None

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _clean_required(value)


class ObservationRead(BaseModel):
    id: UUID
    session_id: UUID
    category: ObservationCategory
    text: str
    source: Literal["user", "ai_proposed"]
    review_state: Literal["confirmed", "proposed", "rejected"]
    fastener_id: UUID | None
    created_at: datetime


class PhotoEvidenceRead(BaseModel):
    id: UUID
    session_id: UUID
    purpose: PhotoPurpose
    observation_id: UUID | None
    fastener_id: UUID | None
    original_filename: str | None
    media_type: str
    byte_size: int
    sha256: str
    content_url: str
    created_at: datetime


class PhotoDeleteRead(BaseModel):
    id: UUID
    deleted_at: datetime
