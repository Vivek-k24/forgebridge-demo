from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from ..user_vehicle.schemas import UserVehicleRead

SessionStatus = Literal["active", "paused", "archived"]
SessionEventType = Literal[
    "session_started",
    "session_paused",
    "session_resumed",
    "session_archived",
    "storage_location_created",
    "fastener_recorded",
    "fastener_state_changed",
    "inventory_item_recorded",
    "inventory_state_changed",
    "observation_recorded",
    "photo_evidence_added",
    "photo_evidence_deleted",
]
LeaseStatus = Literal["available", "owned", "held_by_other"]


class RepairSessionCreate(BaseModel):
    user_vehicle_id: UUID
    title: str = Field(min_length=1, max_length=160)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("repair session title must not be blank")
        return cleaned


class RepairSessionRead(BaseModel):
    id: UUID
    user_vehicle_id: UUID
    title: str
    status: SessionStatus
    current_sequence: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RepairSessionEventRead(BaseModel):
    id: UUID
    session_id: UUID
    sequence: int
    event_type: SessionEventType
    actor_device_id: UUID
    payload: dict[str, object]
    created_at: datetime


class RepairSessionLeaseRead(BaseModel):
    status: LeaseStatus
    can_edit: bool
    expires_at: datetime | None


class RepairSessionResumeRead(BaseModel):
    session: RepairSessionRead
    vehicle: UserVehicleRead
    last_event: RepairSessionEventRead
    lease: RepairSessionLeaseRead


class RepairSessionMutationRead(BaseModel):
    session: RepairSessionRead
    event: RepairSessionEventRead
    lease: RepairSessionLeaseRead


class RepairSessionLeaseMutationRead(BaseModel):
    session_id: UUID
    lease: RepairSessionLeaseRead


class RepairSessionEventPage(BaseModel):
    items: list[RepairSessionEventRead]
    next_after_sequence: int | None
