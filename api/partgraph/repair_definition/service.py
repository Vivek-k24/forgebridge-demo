from collections import defaultdict
from collections.abc import Collection
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..catalog.source_models import MechanicalClaim
from ..errors import PartGraphError
from .manifest import ManifestConflict, RequirementFact, build_requirement_manifest
from .models import (
    RepairDefinition,
    RepairOperation,
    RequirementDefinition,
    RequirementUse,
    RequirementUseEvidence,
)
from .schemas import RepairDefinitionManifestRead, RequirementManifestItemRead

REPAIR_DEFINITION_NOT_FOUND = "REPAIR_DEFINITION_NOT_FOUND"
REPAIR_DEFINITION_INTEGRITY_ERROR = "REPAIR_DEFINITION_INTEGRITY_ERROR"
REPAIR_DEFINITION_BINDING_INVALID = "REPAIR_DEFINITION_BINDING_INVALID"


def _integrity_error(message: str) -> PartGraphError:
    return PartGraphError(
        code=REPAIR_DEFINITION_INTEGRITY_ERROR,
        message=message,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


async def _manifest_for_definition(
    session: AsyncSession,
    *,
    definition: RepairDefinition,
    allowed_claim_states: Collection[str],
) -> RepairDefinitionManifestRead:
    rows = (
        await session.execute(
            select(RequirementUse, RequirementDefinition, RepairOperation.operation_key)
            .join(
                RequirementDefinition,
                RequirementDefinition.id == RequirementUse.requirement_definition_id,
            )
            .outerjoin(RepairOperation, RepairOperation.id == RequirementUse.operation_id)
            .where(RequirementUse.repair_definition_id == definition.id)
            .order_by(RequirementDefinition.requirement_key, RequirementUse.id)
        )
    ).all()

    use_ids = [row[0].id for row in rows]
    claims_by_use: dict[UUID, set[UUID]] = defaultdict(set)
    if use_ids:
        evidence_rows = (
            await session.execute(
                select(RequirementUseEvidence.requirement_use_id, MechanicalClaim.id)
                .join(
                    MechanicalClaim,
                    MechanicalClaim.id == RequirementUseEvidence.mechanical_claim_id,
                )
                .where(
                    RequirementUseEvidence.requirement_use_id.in_(use_ids),
                    MechanicalClaim.promotion_state.in_(allowed_claim_states),
                    MechanicalClaim.claim_domain == "repair_requirement",
                    MechanicalClaim.exact_applicability.is_(True),
                    MechanicalClaim.vehicle_configuration_id == definition.vehicle_configuration_id,
                    MechanicalClaim.repair_key == definition.repair_key,
                )
            )
        ).all()
        for use_id, claim_id in evidence_rows:
            claims_by_use[use_id].add(claim_id)

    missing_evidence = [use_id for use_id in use_ids if not claims_by_use[use_id]]
    if missing_evidence:
        raise _integrity_error(
            "Repair definition contains requirement uses without exact verified evidence."
        )

    facts = [
        RequirementFact(
            use_id=requirement_use.id,
            requirement_key=requirement.requirement_key,
            category=requirement.category,
            display_name=requirement.display_name,
            quantity=requirement_use.quantity,
            unit=requirement_use.unit,
            necessity=requirement_use.necessity,
            fulfillment_mode=requirement_use.fulfillment_mode,
            timing=requirement_use.timing,
            operation_key=operation_key,
        )
        for requirement_use, requirement, operation_key in rows
    ]
    try:
        manifest = build_requirement_manifest(facts)
    except ManifestConflict as exc:
        raise _integrity_error(
            "Repair requirements conflict and require canonical review."
        ) from exc

    requirement_ids = {
        requirement.requirement_key: requirement.id
        for _, requirement, _ in rows
    }
    items: list[RequirementManifestItemRead] = []
    for item in manifest:
        requirement_definition_id = requirement_ids.get(item.requirement_key)
        if requirement_definition_id is None:
            raise _integrity_error("Repair manifest lost its canonical requirement identity.")
        supporting_claim_ids = sorted(
            {
                claim_id
                for use_id in item.supporting_use_ids
                for claim_id in claims_by_use[use_id]
            },
            key=str,
        )
        items.append(
            RequirementManifestItemRead(
                requirement_definition_id=requirement_definition_id,
                requirement_key=item.requirement_key,
                category=item.category,
                display_name=item.display_name,
                required_quantity=item.required_quantity,
                unit=item.unit,
                necessity=item.necessity,
                fulfillment_mode=item.fulfillment_mode,
                operation_keys=list(item.operation_keys),
                supporting_use_ids=list(item.supporting_use_ids),
                supporting_claim_ids=supporting_claim_ids,
            )
        )

    if definition.status not in {"verified", "superseded"}:
        raise _integrity_error(
            "Repair manifest was requested from a non-verifiable definition state."
        )

    return RepairDefinitionManifestRead(
        repair_definition_id=definition.id,
        vehicle_configuration_id=definition.vehicle_configuration_id,
        repair_key=definition.repair_key,
        title=definition.title,
        version=definition.version,
        definition_status=definition.status,
        requirements=items,
    )


async def verified_requirement_manifest(
    session: AsyncSession,
    *,
    vehicle_configuration_id: UUID,
    repair_key: str,
) -> RepairDefinitionManifestRead:
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
            code=REPAIR_DEFINITION_NOT_FOUND,
            message="No verified repair definition exists for this exact vehicle configuration.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if len(definitions) != 1:
        raise _integrity_error(
            "Multiple current verified repair definitions exist for the same vehicle and repair."
        )
    return await _manifest_for_definition(
        session,
        definition=definitions[0],
        allowed_claim_states={"verified"},
    )


async def bound_requirement_manifest(
    session: AsyncSession,
    *,
    repair_definition_id: UUID,
    vehicle_configuration_id: UUID,
) -> RepairDefinitionManifestRead:
    definition = await session.scalar(
        select(RepairDefinition).where(
            RepairDefinition.id == repair_definition_id,
            RepairDefinition.vehicle_configuration_id == vehicle_configuration_id,
        )
    )
    if definition is None or definition.status not in {"verified", "superseded"}:
        raise PartGraphError(
            code=REPAIR_DEFINITION_BINDING_INVALID,
            message="Bound repair definition no longer matches the session vehicle configuration.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return await _manifest_for_definition(
        session,
        definition=definition,
        allowed_claim_states={"verified", "superseded"},
    )
