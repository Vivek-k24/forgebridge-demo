import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from partgraph.catalog.models import CatalogVerifiedEvidence
from partgraph.catalog.source_models import CatalogSource, MechanicalClaim
from partgraph.database import session_factory
from partgraph.main import app
from partgraph.repair_definition.models import (
    RepairDefinition,
    RepairOperation,
    RequirementDefinition,
    RequirementUse,
    RequirementUseEvidence,
)
from partgraph.vehicle.schemas import VehicleConfigurationInput
from partgraph.vehicle.service import resolve_configuration


def seed_verified_repair() -> tuple[UUID, str]:
    async def seed() -> tuple[UUID, str]:
        suffix = uuid4().hex[:10]
        repair_key = f"cooling-system-service-{suffix}"
        now = datetime.now(UTC)
        async with session_factory() as session:
            configuration, _ = await resolve_configuration(
                session,
                VehicleConfigurationInput(
                    year=2009,
                    market="US",
                    make="Honda",
                    model=f"Civic-{suffix}",
                    generation="8",
                    trim="Hybrid",
                    body_style="Sedan",
                    engine="1.3L I4 Hybrid",
                    transmission="CVT",
                    drivetrain="FWD",
                ),
            )
            source = CatalogSource(
                source_key=f"fixture-oem-{suffix}",
                display_name="Deterministic OEM fixture",
                source_class="oem_service",
                license_status="approved",
                automation_allowed=False,
            )
            evidence = CatalogVerifiedEvidence(
                staging_record_id=uuid4(),
                candidate_type="repair_requirement",
                verified_payload={"fixture": True},
                vehicle_identity={"configuration_id": str(configuration.id)},
                source_name="fixture-oem",
                source_type="oem_service",
                source_record_id=f"procedure-{suffix}",
                source_url="https://example.invalid/oem-fixture",
                raw_sha256="a" * 64,
                fetched_at=now,
                observed_at=now,
                provenance={"section": "fixture"},
                extraction_method="deterministic_fixture",
                promoted_by="test-suite",
            )
            session.add_all([source, evidence])
            await session.flush()

            claim = MechanicalClaim(
                source_id=source.id,
                verified_evidence_id=evidence.id,
                vehicle_configuration_id=configuration.id,
                claim_domain="repair_requirement",
                claim_risk="normal",
                normalized_key=f"repair:{repair_key}:requirements",
                repair_key=repair_key,
                claim_payload={"fixture": True},
                explicit_claim=True,
                exact_applicability=True,
                promotion_state="verified",
                reviewed_at=now,
                reviewed_by="test-suite",
            )
            definition = RepairDefinition(
                vehicle_configuration_id=configuration.id,
                repair_key=repair_key,
                title="Cooling system service",
                version=1,
                status="verified",
                verified_at=now,
            )
            socket = RequirementDefinition(
                requirement_key=f"tool.socket.10mm.{suffix}",
                category="tool",
                display_name="10 mm socket",
                default_unit="each",
            )
            coolant = RequirementDefinition(
                requirement_key=f"fluid.coolant.{suffix}",
                category="fluid",
                display_name="Approved coolant",
                default_unit="L",
            )
            session.add_all([claim, definition, socket, coolant])
            await session.flush()

            drain = RepairOperation(
                repair_definition_id=definition.id,
                operation_key="drain",
                label="Drain cooling system",
                position=0,
            )
            refill = RepairOperation(
                repair_definition_id=definition.id,
                operation_key="refill",
                label="Refill cooling system",
                position=1,
            )
            session.add_all([drain, refill])
            await session.flush()

            uses = [
                RequirementUse(
                    repair_definition_id=definition.id,
                    operation_id=drain.id,
                    requirement_definition_id=socket.id,
                    quantity=Decimal("1"),
                    unit="each",
                    necessity="required",
                    fulfillment_mode="reusable",
                    timing="operation",
                ),
                RequirementUse(
                    repair_definition_id=definition.id,
                    operation_id=refill.id,
                    requirement_definition_id=socket.id,
                    quantity=Decimal("1"),
                    unit="each",
                    necessity="required",
                    fulfillment_mode="reusable",
                    timing="operation",
                ),
                RequirementUse(
                    repair_definition_id=definition.id,
                    operation_id=refill.id,
                    requirement_definition_id=coolant.id,
                    quantity=Decimal("2.5"),
                    unit="L",
                    necessity="required",
                    fulfillment_mode="consumed",
                    timing="operation",
                ),
            ]
            session.add_all(uses)
            await session.flush()
            session.add_all(
                [
                    RequirementUseEvidence(
                        requirement_use_id=use.id,
                        mechanical_claim_id=claim.id,
                    )
                    for use in uses
                ]
            )
            await session.commit()
            return configuration.id, repair_key

    return asyncio.run(seed())


def test_verified_manifest_is_exact_evidence_backed_and_deterministic() -> None:
    configuration_id, repair_key = seed_verified_repair()

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/vehicle-configurations/{configuration_id}/repairs/{repair_key}/requirements"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["vehicle_configuration_id"] == str(configuration_id)
    assert body["repair_key"] == repair_key
    assert body["version"] == 1
    assert [item["category"] for item in body["requirements"]] == ["fluid", "tool"]
    fluid, tool = body["requirements"]
    assert Decimal(fluid["required_quantity"]) == Decimal("2.5")
    assert fluid["fulfillment_mode"] == "consumed"
    assert Decimal(tool["required_quantity"]) == Decimal("1")
    assert tool["fulfillment_mode"] == "reusable"
    assert tool["operation_keys"] == ["drain", "refill"]
    assert len(tool["supporting_use_ids"]) == 2
    assert len(tool["supporting_claim_ids"]) == 1


def test_manifest_does_not_fall_back_to_another_vehicle_or_repair() -> None:
    configuration_id, repair_key = seed_verified_repair()

    with TestClient(app) as client:
        wrong_repair = client.get(
            f"/api/v1/vehicle-configurations/{configuration_id}/repairs/not-{repair_key}/requirements"
        )
        wrong_vehicle = client.get(
            f"/api/v1/vehicle-configurations/{uuid4()}/repairs/{repair_key}/requirements"
        )

    for response in (wrong_repair, wrong_vehicle):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "REPAIR_DEFINITION_NOT_FOUND"
