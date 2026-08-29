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
    "readiness_state_changed",
    "observation_recorded",
    "photo_evidence_added",
    "photo_evidence_deleted",
]
LeaseStatus = Literal["available", "owned", "held_by_other"]
ResumeAttentionKind = Literal["fastener", "inventory", "observation"]
ResumeAttentionSeverity = Literal["attention", "waiting", "blocking"]
NextVerifiedActionStatus = Literal["available", "unavailable"]


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


class ResumeActivityRead(BaseModel):
    sequence: int
    event_type: SessionEventType
    label: str
    created_at: datetime


class ResumeAttentionItemRead(BaseModel):
    kind: ResumeAttentionKind
    id: UUID
    label: str
    state: str
    severity: ResumeAttentionSeverity
    detail: str | None = None


class ResumeStorageGroupRead(BaseModel):
    storage_location_id: UUID
    label: str
    item_count: int


class ResumeObservationRead(BaseModel):
    id: UUID
    category: str
    text: str
    fastener_id: UUID | None
    created_at: datetime


class ResumeEvidenceRead(BaseModel):
    id: UUID
    purpose: str
    content_url: str
    created_at: datetime


class ResumeCountsRead(BaseModel):
    fasteners_total: int
    hardware_not_installed: int
    hardware_stored: int
    hardware_loose: int
    inventory_total: int
    procurement_blockers: int
    observations_total: int
    photos_total: int


class ResumeNextVerifiedActionRead(BaseModel):
    status: NextVerifiedActionStatus
    label: str | None = None
    reason: str | None = None


class RepairSessionReorientationRead(BaseModel):
    checkpoint: ResumeActivityRead
    attention: list[ResumeAttentionItemRead]
    storage_groups: list[ResumeStorageGroupRead]
    recent_observations: list[ResumeObservationRead]
    recent_evidence: list[ResumeEvidenceRead]
    recent_activity: list[ResumeActivityRead]
    counts: ResumeCountsRead
    next_verified_action: ResumeNextVerifiedActionRead


class RepairSessionResumeRead(BaseModel):
    session: RepairSessionRead
    vehicle: UserVehicleRead
    last_event: RepairSessionEventRead
    lease: RepairSessionLeaseRead
    reorientation: RepairSessionReorientationRead | None = None


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
