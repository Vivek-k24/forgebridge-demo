from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ..errors import ErrorCode, PartGraphError
from .models import MechanicalClaim
from .support_boundaries import ProcedureBoundaryAction, validate_computer_service_boundary

RequirementCategory = Literal[
    "tool",
    "equipment",
    "part",
    "fluid",
    "consumable",
    "hardware",
    "workspace",
    "safety_prerequisite",
]
RequirementNecessity = Literal["required", "recommended"]
FulfillmentMode = Literal[
    "reusable",
    "consumed",
    "reuse_existing",
    "replacement_required",
    "replace_if_damaged",
]
RequirementTiming = Literal["before_start", "whole_repair", "operation"]

_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


def _normalize_key(value: str, field_name: str, maximum: int) -> str:
    normalized = value.strip().lower()
    if not normalized or len(normalized) > maximum or _KEY_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"{field_name} must be a normalized lowercase key")
    return normalized


def _normalize_text(value: str, field_name: str, maximum: int) -> str:
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > maximum:
        raise ValueError(f"{field_name} must contain 1-{maximum} characters")
    return normalized


class RepairOperationMaterializationSpec(BaseModel):
    operation_key: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=180)
    position: int = Field(ge=0)

    @model_validator(mode="after")
    def normalize(self) -> RepairOperationMaterializationSpec:
        self.operation_key = _normalize_key(self.operation_key, "operation_key", 120)
        self.label = _normalize_text(self.label, "label", 180)
        return self


class RequirementMaterializationSpec(BaseModel):
    use_key: str = Field(min_length=1, max_length=120)
    requirement_key: str = Field(min_length=1, max_length=160)
    category: RequirementCategory
    display_name: str = Field(min_length=1, max_length=180)
    default_unit: str | None = Field(default=None, max_length=32)
    quantity: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=32)
    necessity: RequirementNecessity = "required"
    fulfillment_mode: FulfillmentMode
    timing: RequirementTiming
    operation_key: str | None = Field(default=None, max_length=120)
    supporting_claim_ids: list[UUID] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_scope(self) -> RequirementMaterializationSpec:
        self.use_key = _normalize_key(self.use_key, "use_key", 120)
        self.requirement_key = _normalize_key(self.requirement_key, "requirement_key", 160)
        self.display_name = _normalize_text(self.display_name, "display_name", 180)
        if self.default_unit is not None:
            self.default_unit = _normalize_text(self.default_unit, "default_unit", 32)
        if self.unit is not None:
            self.unit = _normalize_text(self.unit, "unit", 32)
        if self.operation_key is not None:
            self.operation_key = _normalize_key(self.operation_key, "operation_key", 120)
        if self.timing == "operation" and self.operation_key is None:
            raise ValueError("operation_key is required when timing is operation")
        if self.timing != "operation" and self.operation_key is not None:
            raise ValueError("operation_key is only valid when timing is operation")
        if len(set(self.supporting_claim_ids)) != len(self.supporting_claim_ids):
            raise ValueError("supporting_claim_ids cannot contain duplicates")
        return self


class ProcedureActionMaterializationSpec(BaseModel):
    action_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=180)
    instruction: str = Field(min_length=1, max_length=4000)
    warning_text: str | None = Field(default=None, max_length=2000)
    workspace_note: str | None = Field(default=None, max_length=1000)
    position: int = Field(ge=0)
    skippable: bool = False
    prerequisite_action_keys: list[str] = Field(default_factory=list, max_length=64)
    requirement_use_keys: list[str] = Field(default_factory=list, max_length=128)
    supporting_claim_ids: list[UUID] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def normalize(self) -> ProcedureActionMaterializationSpec:
        self.action_key = _normalize_key(self.action_key, "action_key", 120)
        self.title = _normalize_text(self.title, "title", 180)
        self.instruction = _normalize_text(self.instruction, "instruction", 4000)
        if self.warning_text is not None:
            self.warning_text = _normalize_text(self.warning_text, "warning_text", 2000)
        if self.workspace_note is not None:
            self.workspace_note = _normalize_text(self.workspace_note, "workspace_note", 1000)
        self.prerequisite_action_keys = [
            _normalize_key(item, "prerequisite_action_key", 120)
            for item in self.prerequisite_action_keys
        ]
        self.requirement_use_keys = [
            _normalize_key(item, "requirement_use_key", 120)
            for item in self.requirement_use_keys
        ]
        if len(set(self.prerequisite_action_keys)) != len(self.prerequisite_action_keys):
            raise ValueError("prerequisite_action_keys cannot contain duplicates")
        if len(set(self.requirement_use_keys)) != len(self.requirement_use_keys):
            raise ValueError("requirement_use_keys cannot contain duplicates")
        if self.action_key in self.prerequisite_action_keys:
            raise ValueError("an action cannot depend on itself")
        if len(set(self.supporting_claim_ids)) != len(self.supporting_claim_ids):
            raise ValueError("supporting_claim_ids cannot contain duplicates")
        return self


class RepairDefinitionMaterializationCreate(BaseModel):
    vehicle_configuration_id: UUID
    repair_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=180)
    capability_policy_key: str = Field(min_length=1, max_length=120)
    expected_current_definition_id: UUID | None = None
    operations: list[RepairOperationMaterializationSpec] = Field(default_factory=list, max_length=128)
    requirements: list[RequirementMaterializationSpec] = Field(default_factory=list, max_length=512)
    actions: list[ProcedureActionMaterializationSpec] = Field(default_factory=list, max_length=512)

    @model_validator(mode="after")
    def validate_graph(self) -> RepairDefinitionMaterializationCreate:
        self.repair_key = _normalize_key(self.repair_key, "repair_key", 120)
        self.title = _normalize_text(self.title, "title", 180)
        self.capability_policy_key = _normalize_key(
            self.capability_policy_key, "capability_policy_key", 120
        )
        if not self.requirements and not self.actions:
            raise ValueError("a repair definition must contain requirements or procedure actions")

        operations_by_key = _unique_map(
            self.operations, "operation_key", lambda item: item.operation_key
        )
        _unique_positions(self.operations, "operation")
        requirements_by_use = _unique_map(
            self.requirements, "use_key", lambda item: item.use_key
        )
        actions_by_key = _unique_map(
            self.actions, "action_key", lambda item: item.action_key
        )
        _unique_positions(self.actions, "procedure action")

        metadata_by_requirement: dict[str, tuple[str, str, str | None]] = {}
        referenced_operations: set[str] = set()
        for requirement in self.requirements:
            metadata = (
                requirement.category,
                requirement.display_name,
                requirement.default_unit,
            )
            previous = metadata_by_requirement.setdefault(requirement.requirement_key, metadata)
            if previous != metadata:
                raise ValueError(
                    "repeated requirement_key values must use identical canonical metadata"
                )
            if requirement.operation_key is not None:
                if requirement.operation_key not in operations_by_key:
                    raise ValueError("requirement references an unknown operation_key")
                referenced_operations.add(requirement.operation_key)
        if set(operations_by_key) != referenced_operations:
            raise ValueError("every operation must be referenced by an operation-scoped requirement")

        for action in self.actions:
            for prerequisite_key in action.prerequisite_action_keys:
                prerequisite = actions_by_key.get(prerequisite_key)
                if prerequisite is None:
                    raise ValueError("procedure action references an unknown prerequisite")
                if prerequisite.position >= action.position:
                    raise ValueError(
                        "procedure prerequisites must occur before the dependent action"
                    )
            for use_key in action.requirement_use_keys:
                if use_key not in requirements_by_use:
                    raise ValueError("procedure action references an unknown requirement use")

        validate_computer_service_boundary(
            ProcedureBoundaryAction(
                action_key=action.action_key,
                position=action.position,
                skippable=action.skippable,
            )
            for action in self.actions
        )
        return self


class RepairDefinitionMaterializationRead(BaseModel):
    repair_definition_id: UUID
    vehicle_configuration_id: UUID
    repair_key: str
    version: int
    definition_status: Literal["verified", "superseded"]
    canonical_record_version_id: UUID
    superseded_definition_id: UUID | None
    supporting_claim_ids: list[UUID]
    idempotent: bool = False


def _unique_map(items: list[object], field_name: str, key) -> dict[str, object]:
    result: dict[str, object] = {}
    for item in items:
        value = key(item)
        if value in result:
            raise ValueError(f"{field_name} values must be unique")
        result[value] = item
    return result


def _unique_positions(
    items: list[RepairOperationMaterializationSpec] | list[ProcedureActionMaterializationSpec],
    label: str,
) -> None:
    positions = [item.position for item in items]
    if len(set(positions)) != len(positions):
        raise ValueError(f"{label} positions must be unique")


def invalid_materialization(
    message: str,
    *,
    details: dict[str, object] | None = None,
) -> PartGraphError:
    return PartGraphError(
        code=ErrorCode.KNOWLEDGE_MATERIALIZATION_INVALID,
        message=message,
        status_code=409,
        details=details,
    )


def request_sha256(request: RepairDefinitionMaterializationCreate) -> str:
    payload = json.dumps(
        request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _value_matches(actual: object, expected: object) -> bool:
    if isinstance(expected, Decimal):
        if isinstance(actual, bool):
            return False
        try:
            return Decimal(str(actual)) == expected
        except (InvalidOperation, ValueError):
            return False
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        return sorted(str(item) for item in actual) == sorted(str(item) for item in expected)
    return actual == expected


def assert_payload_coverage(
    claims: list[MechanicalClaim],
    expected: dict[str, object],
    *,
    fact_label: str,
) -> None:
    for field_name, expected_value in expected.items():
        observed = [
            claim.claim_payload[field_name]
            for claim in claims
            if field_name in claim.claim_payload
        ]
        if not observed:
            raise invalid_materialization(
                f"Verified claims do not explicitly support {fact_label}.{field_name}."
            )
        if any(not _value_matches(value, expected_value) for value in observed):
            raise invalid_materialization(
                f"Verified claims contradict the requested {fact_label}.{field_name}."
            )


def requirement_expected(spec: RequirementMaterializationSpec) -> dict[str, object]:
    expected: dict[str, object] = {
        "requirement_key": spec.requirement_key,
        "category": spec.category,
        "display_name": spec.display_name,
        "necessity": spec.necessity,
        "fulfillment_mode": spec.fulfillment_mode,
        "timing": spec.timing,
    }
    if spec.default_unit is not None:
        expected["default_unit"] = spec.default_unit
    if spec.quantity is not None:
        expected["quantity"] = spec.quantity
    if spec.unit is not None:
        expected["unit"] = spec.unit
    if spec.operation_key is not None:
        expected["operation_key"] = spec.operation_key
    return expected


def action_expected(spec: ProcedureActionMaterializationSpec) -> dict[str, object]:
    expected: dict[str, object] = {
        "action_key": spec.action_key,
        "title": spec.title,
        "instruction": spec.instruction,
        "position": spec.position,
        "skippable": spec.skippable,
    }
    if spec.warning_text is not None:
        expected["warning_text"] = spec.warning_text
    if spec.workspace_note is not None:
        expected["workspace_note"] = spec.workspace_note
    if spec.prerequisite_action_keys:
        expected["prerequisite_action_keys"] = spec.prerequisite_action_keys
    if spec.requirement_use_keys:
        expected["requirement_use_keys"] = spec.requirement_use_keys
    return expected