from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RequirementManifestItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    requirement_definition_id: UUID
    requirement_key: str
    category: str
    display_name: str
    required_quantity: Decimal | None
    unit: str | None
    necessity: str
    fulfillment_mode: str
    operation_keys: list[str]
    supporting_use_ids: list[UUID]
    supporting_claim_ids: list[UUID]


class RepairDefinitionManifestRead(BaseModel):
    repair_definition_id: UUID
    vehicle_configuration_id: UUID
    repair_key: str
    title: str
    version: int
    definition_status: Literal["verified", "superseded"]
    requirements: list[RequirementManifestItemRead]
