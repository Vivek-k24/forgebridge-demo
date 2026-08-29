import asyncio
from datetime import UTC, datetime
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

CSRF = {"X-PartGraph-CSRF": "1"}
PASSWORD = "correct-horse-battery-staple"


def seed_verified_repairs() -> tuple[UUID, dict[str, object], str, str]:
    async def seed() -> tuple[UUID, dict[str, object], str, str]:
        suffix = uuid4().hex[:10]
        selection: dict[str, object] = {
            "year": 2020,
            "market": "US",
            "make": "Toyota",
            "model": f"Binding-{suffix}",
            "generation": "12",
            "trim": "LE",
            "body_style": "Sedan",
            "engine": "1.8L I4",
            "transmission": "CVT",
            "drivetrain": "FWD",
        }
        first_key = f"cooling-service-{suffix}"
        second_key = f"belt-service-{suffix}"
        now = datetime.now(UTC)

        async with session_factory() as session:
            configuration, _ = await resolve_configuration(
                session,
                VehicleConfigurationInput.model_validate(selection),
            )

            source = CatalogSource(
                source_key=f"binding-fixture-{suffix}",
                display_name="Binding deterministic OEM fixture",
                source_class="oem_service",
                license_status="approved",
                automation_allowed=False,
            )
            session.add(source)
            await session.flush()

            for position, repair_key in enumerate((first_key, second_key)):
                evidence = CatalogVerifiedEvidence(
                    staging_record_id=uuid4(),
                    candidate_type="repair_requirement",
                    verified_payload={"fixture": True, "repair_key": repair_key},
                    vehicle_identity={"configuration_id": str(configuration.id)},
                    source_name="binding-fixture",
                    source_type="oem_service",
                    source_record_id=f"procedure-{repair_key}",
                    source_url="https://example.invalid/binding-fixture",
                    raw_sha256=("a" if position == 0 else "b") * 64,
                    fetched_at=now,
                    observed_at=now,
                    provenance={"section": f"fixture-{position}"},
                    extraction_method="deterministic_fixture",
                    promoted_by="test-suite",
                )
                session.add(evidence)
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
                    title=f"Verified repair {position + 1}",
                    version=1,
                    status="verified",
                    verified_at=now,
                )
                requirement = RequirementDefinition(
                    requirement_key=f"tool.binding.{suffix}.{position}",
                    category="tool",
                    display_name=f"Fixture tool {position + 1}",
                    default_unit="each",
                )
                session.add_all([claim, definition, requirement])
                await session.flush()

                operation = RepairOperation(
                    repair_definition_id=definition.id,
                    operation_key="prepare",
                    label="Prepare repair",
                    position=0,
                )
                session.add(operation)
                await session.flush()

                requirement_use = RequirementUse(
                    repair_definition_id=definition.id,
                    operation_id=operation.id,
                    requirement_definition_id=requirement.id,
                    quantity=1,
                    unit="each",
                    necessity="required",
                    fulfillment_mode="reusable",
                    timing="operation",
                )
                session.add(requirement_use)
                await session.flush()
                session.add(
                    RequirementUseEvidence(
                        requirement_use_id=requirement_use.id,
                        mechanical_claim_id=claim.id,
                    )
                )

            await session.commit()
            return configuration.id, selection, first_key, second_key

    return asyncio.run(seed())


def register(client: TestClient, prefix: str) -> str:
    suffix = uuid4().hex[:12]
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{prefix}-{suffix}@example.com",
            "username": f"{prefix}_{suffix}"[:32],
            "password": PASSWORD,
        },
        headers=CSRF,
    )
    assert response.status_code == 200, response.text
    return response.json()["user"]["id"]


def create_vehicle(client: TestClient, selection: dict[str, object]) -> str:
    response = client.post(
        "/api/v1/user-vehicles/manual",
        json={"nickname": "Binding test car", "selection": selection},
        headers=CSRF,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_session(client: TestClient, vehicle_id: str, device_id: str) -> str:
    response = client.post(
        "/api/v1/repair-sessions",
        json={"user_vehicle_id": vehicle_id, "title": "User-entered unrelated title"},
        headers={
            **CSRF,
            "X-PartGraph-Device-ID": device_id,
            "Idempotency-Key": f"bind_session_{uuid4().hex[:16]}",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["session"]["id"]


def bind_headers(device_id: str) -> dict[str, str]:
    return {**CSRF, "X-PartGraph-Device-ID": device_id}


def error_code(response) -> str:
    return str(response.json()["error"]["code"])


def test_binding_is_exact_repeatable_and_does_not_advance_physical_history() -> None:
    configuration_id, selection, repair_key, second_repair_key = seed_verified_repairs()
    device_id = str(uuid4())

    with TestClient(app) as client:
        register(client, "binding_owner")
        vehicle_id = create_vehicle(client, selection)
        session_id = create_session(client, vehicle_id, device_id)

        before = client.get(f"/api/v1/repair-sessions/{session_id}/events?limit=100")
        assert before.status_code == 200
        assert [item["event_type"] for item in before.json()["items"]] == ["session_started"]

        bound = client.put(
            f"/api/v1/repair-sessions/{session_id}/repair-definition",
            json={"repair_key": repair_key},
            headers=bind_headers(device_id),
        )
        assert bound.status_code == 200, bound.text
        body = bound.json()
        assert body["binding_state"] == "bound"
        assert body["vehicle_configuration_id"] == str(configuration_id)
        assert body["repair_key"] == repair_key

        repeat = client.put(
            f"/api/v1/repair-sessions/{session_id}/repair-definition",
            json={"repair_key": repair_key},
            headers=bind_headers(device_id),
        )
        assert repeat.status_code == 200, repeat.text
        assert repeat.json()["binding_state"] == "already_bound"
        assert repeat.json()["repair_definition_id"] == body["repair_definition_id"]

        conflict = client.put(
            f"/api/v1/repair-sessions/{session_id}/repair-definition",
            json={"repair_key": second_repair_key},
            headers=bind_headers(device_id),
        )
        assert conflict.status_code == 409
        assert error_code(conflict) == "REPAIR_DEFINITION_BINDING_CONFLICT"

        after = client.get(f"/api/v1/repair-sessions/{session_id}/events?limit=100")
        assert after.status_code == 200
        assert [item["event_type"] for item in after.json()["items"]] == ["session_started"]


def test_binding_requires_canonical_vehicle_and_current_edit_lease() -> None:
    _, selection, repair_key, _ = seed_verified_repairs()
    device_a = str(uuid4())
    device_b = str(uuid4())

    with TestClient(app) as client:
        register(client, "binding_lease")
        vehicle_id = create_vehicle(client, selection)
        session_id = create_session(client, vehicle_id, device_a)

        held = client.put(
            f"/api/v1/repair-sessions/{session_id}/repair-definition",
            json={"repair_key": repair_key},
            headers=bind_headers(device_b),
        )
        assert held.status_code == 409
        assert error_code(held) == "REPAIR_SESSION_LEASE_HELD"

        unresolved = client.post(
            "/api/v1/user-vehicles/manual",
            json={
                "nickname": "Unresolved candidate",
                "selection": {
                    "year": 2020,
                    "market": "US",
                    "make": "Toyota",
                    "model": f"Unknown-{uuid4().hex[:10]}",
                    "trim": "LE",
                },
            },
            headers=CSRF,
        )
        assert unresolved.status_code == 201, unresolved.text
        assert unresolved.json()["canonical_configuration_id"] is None
        unresolved_session = create_session(client, unresolved.json()["id"], device_a)

        rejected = client.put(
            f"/api/v1/repair-sessions/{unresolved_session}/repair-definition",
            json={"repair_key": repair_key},
            headers=bind_headers(device_a),
        )
        assert rejected.status_code == 409
        assert error_code(rejected) == "REPAIR_DEFINITION_VEHICLE_UNRESOLVED"


def test_binding_is_owner_scoped() -> None:
    _, selection, repair_key, _ = seed_verified_repairs()
    device_id = str(uuid4())

    with TestClient(app) as owner, TestClient(app) as stranger:
        register(owner, "binding_private_owner")
        register(stranger, "binding_private_stranger")
        session_id = create_session(owner, create_vehicle(owner, selection), device_id)

        response = stranger.put(
            f"/api/v1/repair-sessions/{session_id}/repair-definition",
            json={"repair_key": repair_key},
            headers=bind_headers(device_id),
        )
        assert response.status_code == 404
        assert error_code(response) == "REPAIR_SESSION_NOT_FOUND"
