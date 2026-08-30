from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from partgraph.catalog.models import CatalogVerifiedEvidence
from partgraph.catalog.source_models import CatalogSource, MechanicalClaim
from partgraph.database import session_factory
from partgraph.repair_definition.models import (
    ProcedureAction,
    ProcedureActionDependency,
    ProcedureActionEvidence,
    ProcedureActionRequirementUse,
    RepairDefinition,
    RequirementDefinition,
    RequirementUse,
    RequirementUseEvidence,
)
from partgraph.vehicle.schemas import VehicleConfigurationInput
from partgraph.vehicle.service import resolve_configuration

DIY_SUPPORTED = UUID("11111111-1111-4111-8111-111111111111")
GUIDED_PROHIBITED = UUID("33333333-3333-4333-8333-333333333333")
SUPPORTED_REPAIR_KEY = "ci-guided-service"
PROHIBITED_REPAIR_KEY = "ci-guided-prohibited"

SELECTION = {
    "year": 2009,
    "market": "US",
    "make": "Honda",
    "model": "Civic",
    "generation": "8",
    "trim": "Hybrid",
    "body_style": "Sedan",
    "engine": "1.3L I4 Hybrid",
    "transmission": "CVT",
    "drivetrain": "FWD",
}


async def add_definition(
    *,
    db,
    configuration_id,
    source: CatalogSource,
    evidence: CatalogVerifiedEvidence,
    repair_key: str,
    title: str,
    capability_policy_id: UUID,
    suffix: str,
) -> tuple[UUID, UUID, UUID]:
    now = datetime.now(UTC)
    definition = RepairDefinition(
        vehicle_configuration_id=configuration_id,
        capability_policy_id=capability_policy_id,
        repair_key=repair_key,
        title=title,
        version=1,
        status="verified",
        verified_at=now,
    )
    requirement = RequirementDefinition(
        requirement_key=f"tool.ci.block11.{suffix}",
        category="tool",
        display_name=f"Synthetic CI {suffix} tool",
        default_unit="each",
    )
    db.add_all([definition, requirement])
    await db.flush()

    requirement_claim = MechanicalClaim(
        source_id=source.id,
        verified_evidence_id=evidence.id,
        vehicle_configuration_id=configuration_id,
        claim_domain="repair_requirement",
        claim_risk="normal",
        normalized_key=f"repair:{repair_key}:tool",
        repair_key=repair_key,
        claim_payload={"synthetic_ci": True, "requirement": "tool"},
        explicit_claim=True,
        exact_applicability=True,
        promotion_state="verified",
        reviewed_at=now,
        reviewed_by="block11-integration-ci",
    )
    prepare_claim = MechanicalClaim(
        source_id=source.id,
        verified_evidence_id=evidence.id,
        vehicle_configuration_id=configuration_id,
        claim_domain="repair_procedure",
        claim_risk="normal",
        normalized_key=f"repair:{repair_key}:prepare",
        repair_key=repair_key,
        claim_payload={"synthetic_ci": True, "action": "prepare"},
        explicit_claim=True,
        exact_applicability=True,
        promotion_state="verified",
        reviewed_at=now,
        reviewed_by="block11-integration-ci",
    )
    service_claim = MechanicalClaim(
        source_id=source.id,
        verified_evidence_id=evidence.id,
        vehicle_configuration_id=configuration_id,
        claim_domain="repair_procedure",
        claim_risk="normal",
        normalized_key=f"repair:{repair_key}:service",
        repair_key=repair_key,
        claim_payload={"synthetic_ci": True, "action": "service"},
        explicit_claim=True,
        exact_applicability=True,
        promotion_state="verified",
        reviewed_at=now,
        reviewed_by="block11-integration-ci",
    )
    db.add_all([requirement_claim, prepare_claim, service_claim])
    await db.flush()

    requirement_use = RequirementUse(
        repair_definition_id=definition.id,
        operation_id=None,
        requirement_definition_id=requirement.id,
        quantity=Decimal("1"),
        unit="each",
        necessity="required",
        fulfillment_mode="reusable",
        timing="whole_repair",
    )
    prepare = ProcedureAction(
        repair_definition_id=definition.id,
        action_key="prepare",
        title=f"Prepare synthetic CI {suffix} repair",
        instruction=(
            "SYNTHETIC CI ACTION. This exists only to verify PartGraph workflow behavior "
            "and is not mechanical repair guidance."
        ),
        position=0,
        skippable=False,
    )
    service = ProcedureAction(
        repair_definition_id=definition.id,
        action_key="service",
        title=f"Service synthetic CI {suffix} component",
        instruction=(
            "SYNTHETIC CI ACTION. Exercise the verified-guidance state transition only; "
            "this is not mechanical repair guidance."
        ),
        warning_text="Synthetic CI warning only. Do not use as repair advice.",
        position=1,
        skippable=False,
    )
    db.add_all([requirement_use, prepare, service])
    await db.flush()

    db.add_all(
        [
            RequirementUseEvidence(
                requirement_use_id=requirement_use.id,
                mechanical_claim_id=requirement_claim.id,
            ),
            ProcedureActionEvidence(
                action_id=prepare.id,
                mechanical_claim_id=prepare_claim.id,
            ),
            ProcedureActionEvidence(
                action_id=service.id,
                mechanical_claim_id=service_claim.id,
            ),
            ProcedureActionDependency(
                action_id=service.id,
                prerequisite_action_id=prepare.id,
            ),
            ProcedureActionRequirementUse(
                action_id=service.id,
                requirement_use_id=requirement_use.id,
            ),
        ]
    )
    await db.flush()
    return requirement.id, prepare.id, service.id


async def seed() -> None:
    now = datetime.now(UTC)
    async with session_factory() as db:
        configuration, _ = await resolve_configuration(
            db,
            VehicleConfigurationInput.model_validate(SELECTION),
        )

        source = CatalogSource(
            source_key="block11-integration-ci-source",
            display_name="Block 11 synthetic integration fixture",
            source_class="oem_service",
            license_status="approved",
            automation_allowed=False,
            notes="Synthetic CI-only data; never production repair truth.",
        )
        evidence = CatalogVerifiedEvidence(
            staging_record_id=uuid4(),
            candidate_type="block11_integration_ci",
            verified_payload={
                "synthetic_ci": True,
                "warning": "DO NOT USE AS REPAIR INSTRUCTION",
            },
            vehicle_identity={"configuration_id": str(configuration.id)},
            source_name="block11-integration-ci",
            source_type="synthetic_fixture",
            source_record_id="block11-integration-ci",
            source_url="https://example.invalid/block11-integration-ci",
            raw_sha256="b" * 64,
            fetched_at=now,
            observed_at=now,
            provenance={"synthetic_ci": True, "local_only": False},
            extraction_method="deterministic_ci_fixture",
            promoted_by="block11-integration-ci",
        )
        db.add_all([source, evidence])
        await db.flush()

        supported_requirement, supported_prepare, supported_service = await add_definition(
            db=db,
            configuration_id=configuration.id,
            source=source,
            evidence=evidence,
            repair_key=SUPPORTED_REPAIR_KEY,
            title="Synthetic CI guided service",
            capability_policy_id=DIY_SUPPORTED,
            suffix="supported",
        )
        await add_definition(
            db=db,
            configuration_id=configuration.id,
            source=source,
            evidence=evidence,
            repair_key=PROHIBITED_REPAIR_KEY,
            title="Synthetic CI prohibited service",
            capability_policy_id=GUIDED_PROHIBITED,
            suffix="prohibited",
        )
        await db.commit()

    print(
        json.dumps(
            {
                "configuration_id": str(configuration.id),
                "supported_repair_key": SUPPORTED_REPAIR_KEY,
                "prohibited_repair_key": PROHIBITED_REPAIR_KEY,
                "supported_requirement_id": str(supported_requirement),
                "supported_prepare_action_id": str(supported_prepare),
                "supported_service_action_id": str(supported_service),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(seed())
