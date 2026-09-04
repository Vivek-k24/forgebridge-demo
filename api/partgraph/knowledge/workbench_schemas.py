from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

JobStatus = Literal["queued", "running", "paused", "completed", "failed", "cancelled"]


class CatalogCollectionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    make: str
    status: JobStatus
    cursor_position: int
    total_items: int
    processed_items: int
    collected_items: int
    verified_items: int
    last_configuration_id: UUID | None
    last_error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    last_heartbeat_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CatalogWorkbenchLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    level: Literal["info", "warning", "error"]
    event_type: str
    message: str
    details: dict[str, object]
    created_at: datetime


class CatalogWorkbenchSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    vehicle_configuration_id: UUID
    provider: str
    source_url: str
    fetch_status: Literal["success", "failed", "blocked", "not_found"]
    http_status: int | None
    matched_fields: dict[str, object]
    raw_sha256: str | None
    cache_path: str | None
    error: str | None
    fetched_at: datetime | None
    created_at: datetime


class CatalogWorkbenchMakeRead(BaseModel):
    make: str
    candidates: int
    collected: int
    verified: int
    conflicts: int
    collection_percent: float
    verification_percent: float
    latest_job: CatalogCollectionJobRead | None


class CatalogWorkbenchDashboardRead(BaseModel):
    batch_key: str
    label: str
    verification_rule: str
    candidates: int
    collected: int
    verified: int
    conflicts: int
    collection_percent: float
    verification_percent: float
    makes: list[CatalogWorkbenchMakeRead]
