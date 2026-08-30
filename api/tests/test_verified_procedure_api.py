import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from partgraph.catalog.models import CatalogVerifiedEvidence
from partgraph.catalog.source_models import CatalogSource, MechanicalClaim
from partgraph.database import session_factory
from partgraph.main import app
from partgraph.repair_definition.models import (
    ProcedureAction,
    ProcedureActionDependency,
    ProcedureActionEvidence,
    ProcedureActionRequirementUse,
    RepairDefinition,
    RequirementDefinition,
    RequirementUse,
)
from partgraph.vehicle.schemas import VehicleConfigurationInput
from partgraph.vehicle.service import resolve_configuration

DIY_SUPPORTED = UUID("11111111-1111-4111-8111-111111111111")
PROFESSIONAL_REQUIRED = UUID("22222222-2222-4222-8222-222222222222")
GUIDED_PROHIBITED = UUID("33333333-3333-4333-8333-333333333333")


def seed_procedure(
    *,
    capability_policy_id: UUID = DIY_SUPPORTED,
    missing_second_evidence: bool = False,
    invalid_dependency_order: bool = False,
) -> tuple[UUID, str]:
    async def seed() -> tuple[UUID, str]:
        suffix = uuid4().hex[:10]
        repair_key = f"front-service-{suffix}"
        now = datetime.now(UTC)
        async with session_factory() as session:
            configuration, _ = await resolve_configuration(
                session,
                VehicleConfigurationInput(
                    year=2018,
                    market="US",
                    make="Toyota",
                    model=f"Camry-{suffix}",
                    generation="8",
                    trim="SE",
                    body_style="Sedan",
                    engine="2.5L I4",
                    transmission="Automatic",
                    drivetrain="FWD",
                ),
            )
            source = CatalogSource(
                source_key=f"fixture-procedure-{suffix}",
                display_name="Deterministic procedure fixture",
                source_class="oem_service",
                license_status="approved",
                automation_allowed=False,
            )
            evidence = CatalogVerifiedEvidence(
                staging_record_id=uuid4(),
                candidate_type="repair_procedure",
                verified_payload={"fixture": True},
                vehicle_identity={"configuration_id": str(configuration.id)},
                source_name="fixture-oem",
                source_type="oem_service",
                source_record_id=f"procedure-{suffix}",
                source_url="https://example.invalid/procedure-fixture",
                raw_sha256="b" * 64,
                fetched_at=now,
                observed_at=now,
                provenance={"section": "procedure-fixture"},
                extraction_method="deterministic_fixture",
                promoted_by="test-suite",
            )
            session.add_all([source, evidence])
            await session.flush()

            definition = RepairDefinition(
                vehicle_configuration_id=configuration.id,
                capability_policy_id=capability_policy_id,
                repair_key=repair_key,
                title="Front service fixture",
                version=1,
                status="verified",
                verified_at=now,
            )
            session.add(definition)
            await session.flush()

            if capability_policy_id != DIY_SUPPORTED:
                await session.commit()
                return configuration.id, repair_key

            socket = RequirementDefinition(
                requirement_key=f"tool.socket.12mm.{suffix}",
                category="tool",
                display_name="12 mm socket",
                default_unit="each",
            )
            session.add(socket)
            await session.flush()
            socket_use = RequirementUse(
                repair_definition_id=definition.id,
                operation_id=None,
                requirement_definition_id=socket.id,
                quantity=1,
                unit="each",
                necessity="required",
                fulfillment_mode="reusable",
                timing="whole_repair",
            )
            session.add(socket_use)
            await session.flush()

            prepare = ProcedureAction(
                repair_definition_id=definition.id,
                action_key="prepare",
                title="Prepare the work area",
                instruction="Position the vehicle in the verified workspace configuration.",
                warning_text="Keep the work area clear before proceeding.",
                workspace_note="Stable, level work surface required.",
                position=0,
            )
            remove = ProcedureAction(
                repair_definition_id=definition.id,
                action_key="remove-cover",
                title="Remove the service cover",
                instruction="Remove the verified service cover fasteners and retain them.",
                warning_text=None,
                workspace_note=None,
                position=1,
            )
            session.add_all([prepare, remove])
            await session.flush()

            claims = [
                MechanicalClaim(
                    source_id=source.id,
                    verified_evidence_id=evidence.id,
                    vehicle_configuration_id=configuration.id,
                    claim_domain="repair_procedure",
                    claim_risk="normal",
                    normalized_key=f"repair:{repair_key}:prepare",
                    repair_key=repair_key,
                    claim_payload={"action": "prepare"},
                    explicit_claim=True,
                    exact_applicability=True,
                    promotion_state="verified",
                    reviewed_at=now,
                    reviewed_by="test-suite",
                ),
                MechanicalClaim(
                    source_id=source.id,
                    verified_evidence_id=evidence.id,
                    vehicle_configuration_id=configuration.id,
                    claim_domain="repair_procedure",
                    claim_risk="normal",
                    normalized_key=f"repair:{repair_key}:remove-cover",
                    repair_key=repair_key,
                    claim_payload={"action": "remove-cover"},
                    explicit_claim=True,
                    exact_applicability=True,
                    promotion_state="verified",
                    reviewed_at=now,
                    reviewed_by="test-suite",
                ),
            ]
            session.add_all(claims)
            await session.flush()

            session.add(
                ProcedureActionDependency(
                    action_id=remove.id,
                    prerequisite_action_id=prepare.id,
                )
            )
            if invalid_dependency_order:
                session.add(
                    ProcedureActionDependency(
                        action_id=prepare.id,
                        prerequisite_action_id=remove.id,
                    )
                )
            session.add(
                ProcedureActionRequirementUse(
                    action_id=remove.id,
                    requirement_use_id=socket_use.id,
                )
            )
            session.add(
                ProcedureActionEvidence(
                    action_id=prepare.id,
                    mechanical_claim_id=claims[0].id,
                )
            )
            if not missing_second_evidence:
                session.add(
                    ProcedureActionEvidence(
                        action_id=remove.id,
                        mechanical_claim_id=claims[1].id,
                    )
                )
            await session.commit()
            return configuration.id, repair_key

    return asyncio.run(seed())


def test_supported_verified_procedure_is_exact_and_evidence_backed() -> None:
    configuration_id, repair_key = seed_procedure()

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/vehicle-configurations/{configuration_id}/repairs/"
            f"{repair_key}/procedure"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["vehicle_configuration_id"] == str(configuration_id)
    assert body["repair_key"] == repair_key
    assert body["capability_policy_key"] == "diy_supported"
    assert body["guidance_state"] == "supported"
    assert [action["action_key"] for action in body["actions"]] == [
        "prepare",
        "remove-cover",
    ]
    assert body["actions"][0]["dependency_action_keys"] == []
    assert body["actions"][1]["dependency_action_keys"] == ["prepare"]
    assert len(body["actions"][1]["required_use_ids"]) == 1
    assert len(body["actions"][0]["supporting_claim_ids"]) == 1
    assert len(body["actions"][1]["supporting_claim_ids"]) == 1


def test_professional_required_policy_never_returns_action_content() -> None:
    configuration_id, repair_key = seed_procedure(
        capability_policy_id=PROFESSIONAL_REQUIRED
    )

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/vehicle-configurations/{configuration_id}/repairs/"
            f"{repair_key}/procedure"
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REPAIR_GUIDANCE_PROFESSIONAL_REQUIRED"
    assert "instruction" not in response.text


def test_prohibited_policy_never_returns_guided_procedure() -> None:
    configuration_id, repair_key = seed_procedure(
        capability_policy_id=GUIDED_PROHIBITED
    )

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/vehicle-configurations/{configuration_id}/repairs/"
            f"{repair_key}/procedure"
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "REPAIR_GUIDANCE_PROHIBITED"
    assert "instruction" not in response.text


def test_procedure_fails_closed_when_action_lacks_verified_evidence() -> None:
    configuration_id, repair_key = seed_procedure(missing_second_evidence=True)

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/vehicle-configurations/{configuration_id}/repairs/"
            f"{repair_key}/procedure"
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "REPAIR_PROCEDURE_INTEGRITY_ERROR"


def test_procedure_fails_closed_when_dependency_order_is_invalid() -> None:
    configuration_id, repair_key = seed_procedure(invalid_dependency_order=True)

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/vehicle-configurations/{configuration_id}/repairs/"
            f"{repair_key}/procedure"
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "REPAIR_PROCEDURE_INTEGRITY_ERROR"


def test_procedure_never_falls_back_to_another_vehicle_or_repair() -> None:
    configuration_id, repair_key = seed_procedure()

    with TestClient(app) as client:
        wrong_repair = client.get(
            f"/api/v1/vehicle-configurations/{configuration_id}/repairs/"
            f"not-{repair_key}/procedure"
        )
        wrong_vehicle = client.get(
            f"/api/v1/vehicle-configurations/{uuid4()}/repairs/{repair_key}/procedure"
        )

    for response in (wrong_repair, wrong_vehicle):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "REPAIR_PROCEDURE_NOT_AVAILABLE"
