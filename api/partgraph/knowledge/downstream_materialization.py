from __future__ import annotations

import re
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .claim_locks import lock_mechanical_claims
from .completion_models import (
    ProcedureActionMilestone,
    RepairDownstreamRequirement,
    RepairDownstreamRequirementEvidence,
)
from .models import CatalogSource, MechanicalClaim, ProcedureAction, RepairDefinition
from .provenance import CanonicalConflict
from .repair_materialization_contract import assert_payload_coverage, invalid_materialization

TriggerType = Literal["action_completed", "procedure_complete"]
SupportState = Literal["supported", "professional_required", "unsupported"]
MilestoneType = Literal["physical_replacement"]

_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _key(value: str, field: str, maximum: int) -> str:
    cleaned = value.strip().lower()
    if not cleaned or len(cleaned) > maximum or _KEY_PATTERN.fullmatch(cleaned) is None:
        raise ValueError(f"{field} must be a normalized lowercase key")
    return cleaned


def _text(value: str, field: str, maximum: int) -> str:
    cleaned = " ".join(value.split())
    if not cleaned or len(cleaned) > maximum:
        raise ValueError(f"{field} must contain 1-{maximum} characters")
    return cleaned


class DownstreamRequirementMaterializationCreate(BaseModel):
    source_repair_definition_id: UUID
    requirement_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=180)
    detail: str | None = Field(default=None, max_length=2000)
    trigger_type: TriggerType
    trigger_action_key: str | None = Field(default=None, max_length=120)
    support_state: SupportState
    target_repair_definition_id: UUID | None = None
    milestone_type: MilestoneType | None = None
    position: int = Field(ge=0)
    supporting_claim_ids: list[UUID] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def normalize_and_validate(self) -> DownstreamRequirementMaterializationCreate:
        self.requirement_key = _key(self.requirement_key, "requirement_key", 120)
        self.title = _text(self.title, "title", 180)
        if self.detail is not None:
            self.detail = _text(self.detail, "detail", 2000)
        if self.trigger_action_key is not None:
            self.trigger_action_key = _key(
                self.trigger_action_key, "trigger_action_key", 120
            )

        if self.trigger_type == "action_completed":
            if self.trigger_action_key is None:
                raise ValueError("trigger_action_key is required for an action trigger")
        elif self.trigger_action_key is not None:
            raise ValueError("trigger_action_key is only valid for an action trigger")

        if self.support_state == "supported":
            if self.target_repair_definition_id is None:
                raise ValueError(
                    "target_repair_definition_id is required for supported downstream work"
                )
        elif self.target_repair_definition_id is not None:
            raise ValueError(
                "outside-service downstream work cannot target a PartGraph repair definition"
            )

        if self.milestone_type is not None and self.trigger_type != "action_completed":
            raise ValueError("a physical replacement milestone requires an action trigger")
        if len(set(self.supporting_claim_ids)) != len(self.supporting_claim_ids):
            raise ValueError("supporting_claim_ids cannot contain duplicates")
        return self


class DownstreamRequirementMaterializationRead(BaseModel):
    downstream_requirement_id: UUID
    source_repair_definition_id: UUID
    requirement_key: str
    trigger_type: TriggerType
    trigger_action_id: UUID | None
    support_state: SupportState
    target_repair_definition_id: UUID | None
    target_repair_key: str | None
    milestone_type: MilestoneType | None
    supporting_claim_ids: list[UUID]
    idempotent: bool = False


async def _current_verified_definition(
    db: AsyncSession,
    definition_id: UUID,
    *,
    label: str,
) -> RepairDefinition:
    definition = await db.get(RepairDefinition, definition_id)
    if definition is None or definition.status != "verified":
        raise invalid_materialization(f"{label} repair definition is not currently verified.")

    current = list(
        await db.scalars(
            select(RepairDefinition).where(
                RepairDefinition.vehicle_configuration_id
                == definition.vehicle_configuration_id,
                RepairDefinition.repair_key == definition.repair_key,
                RepairDefinition.status == "verified",
            )
        )
    )
    if len(current) != 1 or current[0].id != definition.id:
        raise invalid_materialization(
            f"{label} repair scope does not have exactly one current verified definition."
        )
    return definition


async def _verified_supporting_claims(
    db: AsyncSession,
    request: DownstreamRequirementMaterializationCreate,
    *,
    source: RepairDefinition,
    target: RepairDefinition | None,
) -> list[MechanicalClaim]:
    claim_ids = set(request.supporting_claim_ids)
    await lock_mechanical_claims(db, claim_ids, shared=True)
    claims = list(
        await db.scalars(select(MechanicalClaim).where(MechanicalClaim.id.in_(claim_ids)))
    )
    if {claim.id for claim in claims} != claim_ids:
        raise invalid_materialization(
            "One or more downstream supporting mechanical claims do not exist."
        )

    for claim in claims:
        if (
            claim.promotion_state != "verified"
            or claim.claim_domain != "repair_procedure"
            or not claim.explicit_claim
            or not claim.exact_applicability
            or claim.vehicle_configuration_id != source.vehicle_configuration_id
            or claim.repair_key != source.repair_key
        ):
            raise invalid_materialization(
                "Downstream publication requires verified, explicit, exact repair-procedure "
                "claims for the source repair and vehicle."
            )

    source_ids = {claim.source_id for claim in claims}
    sources = list(
        await db.scalars(select(CatalogSource).where(CatalogSource.id.in_(source_ids)))
    )
    if len(sources) != len(source_ids) or any(
        item.license_status != "approved" for item in sources
    ):
        raise invalid_materialization(
            "Every downstream supporting claim source must still be approved."
        )

    conflict_keys = {claim.conflict_key for claim in claims if claim.conflict_key}
    if conflict_keys:
        blocked = list(
            await db.scalars(
                select(CanonicalConflict.conflict_key).where(
                    CanonicalConflict.conflict_key.in_(conflict_keys),
                    CanonicalConflict.conflict_state.in_(("open", "blocked")),
                )
            )
        )
        if blocked:
            raise invalid_materialization(
                "Downstream supporting claims still have unresolved conflicts.",
                details={"conflict_keys": sorted(blocked)},
            )

    expected: dict[str, object] = {
        "downstream_requirement_key": request.requirement_key,
        "downstream_title": request.title,
        "downstream_trigger_type": request.trigger_type,
        "downstream_support_state": request.support_state,
    }
    if request.detail is not None:
        expected["downstream_detail"] = request.detail
    if request.trigger_action_key is not None:
        expected["downstream_trigger_action_key"] = request.trigger_action_key
    if target is not None:
        expected["downstream_target_repair_key"] = target.repair_key
    if request.milestone_type is not None:
        expected["milestone_type"] = request.milestone_type

    assert_payload_coverage(
        claims,
        expected,
        fact_label=f"downstream[{request.requirement_key}]",
    )
    return claims


async def materialize_downstream_requirement_service(
    db: AsyncSession,
    *,
    request: DownstreamRequirementMaterializationCreate,
) -> DownstreamRequirementMaterializationRead:
    source = await _current_verified_definition(
        db,
        request.source_repair_definition_id,
        label="Source",
    )

    trigger_action: ProcedureAction | None = None
    if request.trigger_type == "action_completed":
        trigger_action = await db.scalar(
            select(ProcedureAction).where(
                ProcedureAction.repair_definition_id == source.id,
                ProcedureAction.action_key == request.trigger_action_key,
            )
        )
        if trigger_action is None:
            raise invalid_materialization(
                "Downstream trigger action is not part of the source repair definition."
            )

    target: RepairDefinition | None = None
    if request.target_repair_definition_id is not None:
        target = await _current_verified_definition(
            db,
            request.target_repair_definition_id,
            label="Target",
        )
        if target.id == source.id:
            raise invalid_materialization("A repair cannot require itself downstream.")
        if target.vehicle_configuration_id != source.vehicle_configuration_id:
            raise invalid_materialization(
                "Supported downstream work must target the same exact vehicle configuration."
            )

    claims = await _verified_supporting_claims(
        db,
        request,
        source=source,
        target=target,
    )

    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"downstream:{source.id}:{request.requirement_key}"},
    )
    existing = await db.scalar(
        select(RepairDownstreamRequirement).where(
            RepairDownstreamRequirement.source_repair_definition_id == source.id,
            RepairDownstreamRequirement.requirement_key == request.requirement_key,
        )
    )

    trigger_action_id = None if trigger_action is None else trigger_action.id
    target_id = None if target is None else target.id
    claim_ids = {claim.id for claim in claims}

    if existing is not None:
        existing_claim_ids = set(
            await db.scalars(
                select(RepairDownstreamRequirementEvidence.mechanical_claim_id).where(
                    RepairDownstreamRequirementEvidence.downstream_requirement_id
                    == existing.id
                )
            )
        )
        milestone = (
            None
            if trigger_action is None
            else await db.get(ProcedureActionMilestone, trigger_action.id)
        )
        existing_milestone = None if milestone is None else milestone.milestone_type
        exact = (
            existing.title == request.title
            and existing.detail == request.detail
            and existing.trigger_type == request.trigger_type
            and existing.trigger_action_id == trigger_action_id
            and existing.support_state == request.support_state
            and existing.target_repair_definition_id == target_id
            and existing.position == request.position
            and existing_claim_ids == claim_ids
            and existing_milestone == request.milestone_type
        )
        if not exact:
            raise invalid_materialization(
                "Existing downstream canonical truth conflicts with this publication request."
            )
        return DownstreamRequirementMaterializationRead(
            downstream_requirement_id=existing.id,
            source_repair_definition_id=source.id,
            requirement_key=existing.requirement_key,
            trigger_type=existing.trigger_type,
            trigger_action_id=existing.trigger_action_id,
            support_state=existing.support_state,
            target_repair_definition_id=existing.target_repair_definition_id,
            target_repair_key=None if target is None else target.repair_key,
            milestone_type=request.milestone_type,
            supporting_claim_ids=sorted(claim_ids, key=str),
            idempotent=True,
        )

    if trigger_action is not None and request.milestone_type is not None:
        milestone = await db.get(ProcedureActionMilestone, trigger_action.id)
        if milestone is None:
            db.add(
                ProcedureActionMilestone(
                    action_id=trigger_action.id,
                    milestone_type=request.milestone_type,
                )
            )
        elif milestone.milestone_type != request.milestone_type:
            raise invalid_materialization(
                "Trigger action already has a conflicting canonical milestone."
            )

    row = RepairDownstreamRequirement(
        id=uuid4(),
        source_repair_definition_id=source.id,
        requirement_key=request.requirement_key,
        title=request.title,
        detail=request.detail,
        trigger_type=request.trigger_type,
        trigger_action_id=trigger_action_id,
        support_state=request.support_state,
        target_repair_definition_id=target_id,
        position=request.position,
    )
    db.add(row)
    await db.flush()

    for claim_id in sorted(claim_ids, key=str):
        db.add(
            RepairDownstreamRequirementEvidence(
                downstream_requirement_id=row.id,
                mechanical_claim_id=claim_id,
            )
        )
    await db.flush()

    return DownstreamRequirementMaterializationRead(
        downstream_requirement_id=row.id,
        source_repair_definition_id=source.id,
        requirement_key=row.requirement_key,
        trigger_type=row.trigger_type,
        trigger_action_id=row.trigger_action_id,
        support_state=row.support_state,
        target_repair_definition_id=row.target_repair_definition_id,
        target_repair_key=None if target is None else target.repair_key,
        milestone_type=request.milestone_type,
        supporting_claim_ids=sorted(claim_ids, key=str),
    )
