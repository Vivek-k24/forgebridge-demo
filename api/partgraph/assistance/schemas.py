from uuid import UUID
from typing import Literal

from pydantic import BaseModel


AssistanceReason = Literal[
    "next_verified_action",
    "current_action_inventory_blocked",
    "current_action_physically_blocked",
    "verified_procedure_complete",
]
GuidanceStatus = Literal[
    "action_available",
    "action_blocked",
    "inventory_blocked",
    "procedure_complete",
]


class AssistanceActionReference(BaseModel):
    action_id: UUID
    action_key: str
    title: str
    dependency_action_keys: list[str]
    supporting_claim_ids: list[UUID]


class AssistanceInventoryBlocker(BaseModel):
    requirement_definition_id: UUID
    requirement_key: str
    display_name: str
    readiness_state: str
    required_quantity: str | None
    unit: str | None


class AssistanceExplanationRead(BaseModel):
    session_id: UUID
    repair_definition_id: UUID
    repair_key: str
    version: int
    guidance_status: GuidanceStatus
    mode: Literal["deterministic"] = "deterministic"
    ai_invoked: Literal[False] = False
    reason_code: AssistanceReason
    headline: str
    explanation: str
    current_action: AssistanceActionReference | None
    inventory_blockers: list[AssistanceInventoryBlocker]
