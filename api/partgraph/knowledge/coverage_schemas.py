from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CatalogCoverageMakeProgress(BaseModel):
    make: str
    candidates: int
    collected: int
    verified: int
    conflict: int
    collection_remaining: int
    verification_remaining: int
    collection_percent: float
    verification_percent: float


class CatalogCoverageBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_key: str
    label: str
    target_rows: int
    verification_rule: str
    status: Literal["collecting", "verifying", "verified", "superseded"]
    scope: dict[str, object]
    candidates: int
    collected: int
    verified: int
    conflict: int
    collection_remaining: int
    verification_remaining: int
    collection_percent: float
    verification_percent: float
    makes: list[CatalogCoverageMakeProgress]
    created_at: datetime
    updated_at: datetime