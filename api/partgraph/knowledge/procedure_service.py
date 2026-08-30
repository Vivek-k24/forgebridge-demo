from collections import defaultdict
from collections.abc import Collection
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import PartGraphError
from .models import (
    MechanicalClaim,
    ProcedureAction,
    ProcedureActionDependency,
    ProcedureActionEvidence,
    ProcedureActionRequirementUse,
    RepairCapabilityPolicy,
    RepairDefinition,
    RequirementUse,
)
from .schemas import ProcedureActionRead, RepairProcedureRead

REPAIR_PROCEDURE_NOT_AVAILABLE = "REPAIR_PROCEDURE_NOT_AVAILABLE"
REPAIR_PROCEDURE_INTEGRITY_ERROR = "REPAIR_PROCEDURE_INTEGRITY_ERROR"
REPAIR_GUIDANCE_PROFESSIONAL_REQUIRED = "REPAIR_GUIDANCE_PROFESSIONAL_REQUIRED"
REPAIR_GUIDANCE_PROHIBITED = "REPAIR_GUIDANCE_PROHIBITED"


def _integrity_error(message: str) -> PartGraphError:
    return PartGraphError(
        code=REPAIR_PROCEDURE_INTEGRITY_ERROR,
        message=message,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _policy_error(policy: RepairCapabilityPolicy) -> PartGraphError:
    if policy.guidance_state == "professional_required":
        return PartGraphError(
            code=REPAIR_GUIDANCE_PROFESSIONAL_REQUIRED,
            message=policy.rationale,
            status_code=status.HTTP_409_CONFLICT,
        )
    if policy.guidance_state == "prohibited":
        return PartGraphError(
            code=REPAIR_GUIDANCE_PROHIBITED,
            message=policy.rationale,
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return _integrity_error("Repair capability policy contains an unknown guidance state.")


def _validate_dependency_graph(
    actions: list[ProcedureAction],
    dependencies: dict[UUID, set[UUID]],
) -> None:
    action_ids = {action.id for action in actions}
    position_by_id = {action.id: action.position for action in actions}

    for action_id, prerequisites in dependencies.items():
        if action_id not in action_ids or not prerequisites.issubset(action_ids):
            raise _integrity_error(
                "Procedure dependency points outside the exact repair definition."
            )
        for prerequisite_id in prerequisites:
            if position_by_id[prerequisite_id] >= position_by_id[action_id]:
                raise _integrity_error(
                    "Procedure dependency order conflicts with canonical action order."
                )

    remaining = {action.id: set(dependencies[action.id]) for action in actions}
    resolved: set[UUID] = set()
    while len(resolved) < len(actions):
        eligible = sorted(
            (
                action
                for action in actions
                if action.id not in resolved and remaining[action.id].issubset(resolved)
            ),
            key=lambda action: (action.position, str(action.id)),
        )
        if not eligible:
            raise _integrity_error(
                "Procedure dependencies contain a cycle or unresolved prerequisite."
            )
        resolved.add(eligible[0].id)


async def _procedure_for_definition(
    session: AsyncSession,
    *,
    definition: RepairDefinition,
    allowed_claim_states: Collection[str],
) -> RepairProcedureRead:
    if definition.capability_policy_id is None:
        raise PartGraphError(
            code=REPAIR_PROCEDURE_NOT_AVAILABLE,
            message="No guided repair capability policy is verified for this repair.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    policy = await session.scalar(
        select(RepairCapabilityPolicy).where(
            RepairCapabilityPolicy.id == definition.capability_policy_id
        )
    )
    if policy is None:
        raise _integrity_error("Repair definition references a missing capability policy.")
    if policy.guidance_state != "supported":
        raise _policy_error(policy)

    actions = list(
        await session.scalars(
            select(ProcedureAction)
            .where(ProcedureAction.repair_definition_id == definition.id)
            .order_by(ProcedureAction.position, ProcedureAction.id)
        )
    )
    if not actions:
        raise PartGraphError(
            code=REPAIR_PROCEDURE_NOT_AVAILABLE,
            message="No verified guided procedure exists for this exact repair definition.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    action_ids = [action.id for action in actions]
    action_by_id = {action.id: action for action in actions}

    dependencies: dict[UUID, set[UUID]] = defaultdict(set)
    for action in actions:
        dependencies[action.id]
    dependency_rows = (
        await session.execute(
            select(
                ProcedureActionDependency.action_id,
                ProcedureActionDependency.prerequisite_action_id,
            ).where(ProcedureActionDependency.action_id.in_(action_ids))
        )
    ).all()
    for action_id, prerequisite_id in dependency_rows:
        dependencies[action_id].add(prerequisite_id)
    _validate_dependency_graph(actions, dependencies)

    requirement_uses: dict[UUID, list[UUID]] = defaultdict(list)
    requirement_rows = (
        await session.execute(
            select(
                ProcedureActionRequirementUse.action_id,
                ProcedureActionRequirementUse.requirement_use_id,
                RequirementUse.repair_definition_id,
            )
            .join(
                RequirementUse,
                RequirementUse.id == ProcedureActionRequirementUse.requirement_use_id,
            )
            .where(ProcedureActionRequirementUse.action_id.in_(action_ids))
        )
    ).all()
    for action_id, requirement_use_id, repair_definition_id in requirement_rows:
        if repair_definition_id != definition.id:
            raise _integrity_error(
                "Procedure action requirement points outside the exact repair definition."
            )
        requirement_uses[action_id].append(requirement_use_id)

    claims_by_action: dict[UUID, set[UUID]] = defaultdict(set)
    evidence_rows = (
        await session.execute(
            select(ProcedureActionEvidence.action_id, MechanicalClaim.id)
            .join(
                MechanicalClaim,
                MechanicalClaim.id == ProcedureActionEvidence.mechanical_claim_id,
            )
            .where(
                ProcedureActionEvidence.action_id.in_(action_ids),
                MechanicalClaim.promotion_state.in_(allowed_claim_states),
                MechanicalClaim.claim_domain == "repair_procedure",
                MechanicalClaim.explicit_claim.is_(True),
                MechanicalClaim.exact_applicability.is_(True),
                MechanicalClaim.vehicle_configuration_id == definition.vehicle_configuration_id,
                MechanicalClaim.repair_key == definition.repair_key,
            )
        )
    ).all()
    for action_id, claim_id in evidence_rows:
        claims_by_action[action_id].add(claim_id)

    missing_evidence = [action.id for action in actions if not claims_by_action[action.id]]
    if missing_evidence:
        raise _integrity_error(
            "Procedure contains actions without exact verified procedure evidence."
        )

    action_reads = [
        ProcedureActionRead(
            action_id=action.id,
            action_key=action.action_key,
            title=action.title,
            instruction=action.instruction,
            warning_text=action.warning_text,
            workspace_note=action.workspace_note,
            position=action.position,
            dependency_action_keys=[
                action_by_id[dependency_id].action_key
                for dependency_id in sorted(
                    dependencies[action.id],
                    key=lambda item: (action_by_id[item].position, str(item)),
                )
            ],
            required_use_ids=sorted(requirement_uses[action.id], key=str),
            supporting_claim_ids=sorted(claims_by_action[action.id], key=str),
        )
        for action in actions
    ]

    return RepairProcedureRead(
        repair_definition_id=definition.id,
        vehicle_configuration_id=definition.vehicle_configuration_id,
        repair_key=definition.repair_key,
        title=definition.title,
        version=definition.version,
        definition_status=definition.status,
        capability_policy_key=policy.policy_key,
        guidance_state=policy.guidance_state,
        policy_title=policy.title,
        policy_rationale=policy.rationale,
        actions=action_reads,
    )


async def verified_procedure_plan(
    session: AsyncSession,
    *,
    vehicle_configuration_id: UUID,
    repair_key: str,
) -> RepairProcedureRead:
    definitions = list(
        await session.scalars(
            select(RepairDefinition)
            .where(
                RepairDefinition.vehicle_configuration_id == vehicle_configuration_id,
                RepairDefinition.repair_key == repair_key,
                RepairDefinition.status == "verified",
            )
            .order_by(RepairDefinition.version.desc())
            .limit(2)
        )
    )
    if not definitions:
        raise PartGraphError(
            code=REPAIR_PROCEDURE_NOT_AVAILABLE,
            message="No verified repair definition exists for this exact vehicle configuration.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if len(definitions) != 1:
        raise _integrity_error(
            "Multiple current verified repair definitions exist for the same vehicle and repair."
        )
    return await _procedure_for_definition(
        session,
        definition=definitions[0],
        allowed_claim_states={"verified"},
    )
