from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProcedureActionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: UUID
    action_key: str
    title: str
    instruction: str
    warning_text: str | None
    workspace_note: str | None
    position: int
    dependency_action_keys: list[str]
    required_use_ids: list[UUID]
    supporting_claim_ids: list[UUID]


class RepairProcedureRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repair_definition_id: UUID
    vehicle_configuration_id: UUID
    repair_key: str
    title: str
    version: int
    definition_status: str
    capability_policy_key: str
    guidance_state: str
    policy_title: str
    policy_rationale: str
    actions: list[ProcedureActionRead]
