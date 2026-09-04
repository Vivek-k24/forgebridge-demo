from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CatalogCoverageMakeProgress(BaseModel):
    make: str
    collected: int
    verified: int
    conflict: int
    remaining: int
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
    collected: int
    verified: int
    conflict: int
    remaining: int
    verification_percent: float
    makes: list[CatalogCoverageMakeProgress]
    created_at: datetime
    updated_at: datetime
