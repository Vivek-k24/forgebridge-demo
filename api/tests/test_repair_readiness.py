import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from partgraph.catalog.models import CatalogVerifiedEvidence
from partgraph.catalog.source_models import CatalogSource, MechanicalClaim
from partgraph.database import session_factory
from partgraph.main import app
from partgraph.repair_definition.models import (
    RepairDefinition,
    RepairOperation,
    RepairRequirementState,
    RequirementDefinition,
    RequirementUse,
    RequirementUseEvidence,
    UserGarageInventoryItem,
)
from partgraph.vehicle.schemas import VehicleConfigurationInput
from partgraph.vehicle.service import resolve_configuration

CSRF = {"X-PartGraph-CSRF": "1"}
PASSWORD = "correct-horse-battery-staple"


def seed_readiness_definition() -> tuple[
    UUID,
    dict[str, object],
    str,
    UUID,
    UUID,
    UUID,
]:
    async def seed() -> tuple[UUID, dict[str, object], str, UUID, UUID, UUID]:
        suffix = uuid4().hex[:10]
        repair_key = f"readiness-service-{suffix}"
        selection: dict[str, object] = {
            "year": 2018,
            "market": "CA",
            "make": "Honda",
            "model": f"Readiness-{suffix}",
            "generation": "10",
            "trim": "LX",
            "body_style": "Sedan",
            "engine": "2.0L I4",
            "transmission": "CVT",
            "drivetrain": "FWD",
        }
        now = datetime.now(UTC)

        async with session_factory() as session:
            configuration, _ = await resolve_configuration(
                session,
                VehicleConfigurationInput.model_validate(selection),
            )
            source = CatalogSource(
                source_key=f"readiness-fixture-{suffix}",
                display_name="Readiness deterministic OEM fixture",
                source_class="oem_service",
                license_status="approved",
                automation_allowed=False,
            )
            evidence = CatalogVerifiedEvidence(
                staging_record_id=uuid4(),
                candidate_type="repair_requirement",
                verified_payload={"fixture": True},
                vehicle_identity={"configuration_id": str(configuration.id)},
                source_name="readiness-fixture",
                source_type="oem_service",
                source_record_id=f"procedure-{suffix}",
                source_url="https://example.invalid/readiness-fixture",
                raw_sha256="c" * 64,
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
                title="Readiness fixture repair",
                version=1,
                status="verified",
                verified_at=now,
            )
            tool = RequirementDefinition(
                requirement_key=f"tool.socket.fixture.{suffix}",
                category="tool",
                display_name="Fixture socket",
                default_unit="each",
            )
            fluid = RequirementDefinition(
                requirement_key=f"fluid.fixture.{suffix}",
                category="fluid",
                display_name="Fixture fluid",
                default_unit="L",
            )
            existing = RequirementDefinition(
                requirement_key=f"hardware.reuse.fixture.{suffix}",
                category="hardware",
                display_name="Existing fixture bracket",
                default_unit="each",
            )
            session.add_all([claim, definition, tool, fluid, existing])
            await session.flush()

            remove = RepairOperation(
                repair_definition_id=definition.id,
                operation_key="remove",
                label="Remove component",
                position=0,
            )
            install = RepairOperation(
                repair_definition_id=definition.id,
                operation_key="install",
                label="Install component",
                position=1,
            )
            session.add_all([remove, install])
            await session.flush()

            uses = [
                RequirementUse(
                    repair_definition_id=definition.id,
                    operation_id=remove.id,
                    requirement_definition_id=tool.id,
                    quantity=Decimal("1"),
                    unit="each",
                    necessity="required",
                    fulfillment_mode="reusable",
                    timing="operation",
                ),
                RequirementUse(
                    repair_definition_id=definition.id,
                    operation_id=install.id,
                    requirement_definition_id=tool.id,
                    quantity=Decimal("1"),
                    unit="each",
                    necessity="required",
                    fulfillment_mode="reusable",
                    timing="operation",
                ),
                RequirementUse(
                    repair_definition_id=definition.id,
                    operation_id=install.id,
                    requirement_definition_id=fluid.id,
                    quantity=Decimal("2.5"),
                    unit="L",
                    necessity="required",
                    fulfillment_mode="consumed",
                    timing="operation",
                ),
                RequirementUse(
                    repair_definition_id=definition.id,
                    operation_id=install.id,
                    requirement_definition_id=existing.id,
                    quantity=Decimal("1"),
                    unit="each",
                    necessity="required",
                    fulfillment_mode="reuse_existing",
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
            return configuration.id, selection, repair_key, definition.id, tool.id, fluid.id

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
        json={"nickname": "Readiness car", "selection": selection},
        headers=CSRF,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_session(client: TestClient, vehicle_id: str, device_id: str) -> str:
    response = client.post(
        "/api/v1/repair-sessions",
        json={"user_vehicle_id": vehicle_id, "title": "Readiness test"},
        headers={
            **CSRF,
            "X-PartGraph-Device-ID": device_id,
            "Idempotency-Key": f"readiness_session_{uuid4().hex[:12]}",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["session"]["id"]


def bind(client: TestClient, session_id: str, device_id: str, repair_key: str) -> None:
    response = client.put(
        f"/api/v1/repair-sessions/{session_id}/repair-definition",
        json={"repair_key": repair_key},
        headers={**CSRF, "X-PartGraph-Device-ID": device_id},
    )
    assert response.status_code == 200, response.text


def test_readiness_is_aggregated_and_uses_garage_then_session_override() -> None:
    _, selection, repair_key, _, tool_id, fluid_id = seed_readiness_definition()
    device_id = str(uuid4())

    with TestClient(app) as client:
        user_id = register(client, "readiness_owner")
        session_id = create_session(client, create_vehicle(client, selection), device_id)

        unbound = client.get(f"/api/v1/repair-sessions/{session_id}/readiness")
        assert unbound.status_code == 200
        assert unbound.json()["binding_status"] == "unbound"
        assert unbound.json()["requirements"] == []

        bind(client, session_id, device_id, repair_key)
        initial = client.get(f"/api/v1/repair-sessions/{session_id}/readiness")
        assert initial.status_code == 200, initial.text
        body = initial.json()
        assert body["binding_status"] == "bound"
        assert body["summary"] == {
            "total": 3,
            "ready": 1,
            "missing": 2,
            "ordered": 0,
            "unavailable": 0,
            "blocked": 2,
        }
        by_category = {item["category"]: item for item in body["requirements"]}
        assert by_category["tool"]["readiness_state"] == "missing"
        assert by_category["tool"]["operation_keys"] == ["install", "remove"]
        assert by_category["fluid"]["readiness_state"] == "missing"
        assert by_category["hardware"]["readiness_state"] == "have"
        assert by_category["hardware"]["readiness_source"] == "existing_vehicle"

        async def add_private_state() -> None:
            async with session_factory() as session:
                session.add(
                    UserGarageInventoryItem(
                        user_id=UUID(user_id),
                        requirement_definition_id=tool_id,
                        quantity_available=Decimal("1"),
                        unit="each",
                    )
                )
                session.add(
                    RepairRequirementState(
                        user_id=UUID(user_id),
                        session_id=UUID(session_id),
                        requirement_definition_id=fluid_id,
                        quantity_available=Decimal("1"),
                        readiness_state="ordered",
                        procurement_reference="fixture-order",
                    )
                )
                await session.commit()

        asyncio.run(add_private_state())
        reconciled = client.get(f"/api/v1/repair-sessions/{session_id}/readiness")
        assert reconciled.status_code == 200, reconciled.text
        items = {item["category"]: item for item in reconciled.json()["requirements"]}
        assert items["tool"]["readiness_state"] == "have"
        assert items["tool"]["readiness_source"] == "garage"
        assert items["fluid"]["readiness_state"] == "ordered"
        assert items["fluid"]["readiness_source"] == "session"
        assert items["fluid"]["procurement_reference"] == "fixture-order"
        assert reconciled.json()["summary"] == {
            "total": 3,
            "ready": 2,
            "missing": 0,
            "ordered": 1,
            "unavailable": 0,
            "blocked": 1,
        }


def test_bound_readiness_remains_version_pinned_when_definition_is_superseded() -> None:
    _, selection, repair_key, definition_id, _, _ = seed_readiness_definition()
    device_id = str(uuid4())

    with TestClient(app) as client:
        register(client, "readiness_pinned")
        session_id = create_session(client, create_vehicle(client, selection), device_id)
        bind(client, session_id, device_id, repair_key)

        async def supersede() -> None:
            async with session_factory() as session:
                definition = await session.get(RepairDefinition, definition_id)
                assert definition is not None
                definition.status = "superseded"
                claim = await session.scalar(
                    select(MechanicalClaim).where(MechanicalClaim.repair_key == repair_key)
                )
                assert claim is not None
                claim.promotion_state = "superseded"
                await session.commit()

        asyncio.run(supersede())
        response = client.get(f"/api/v1/repair-sessions/{session_id}/readiness")
        assert response.status_code == 200, response.text
        assert response.json()["repair"]["repair_definition_id"] == str(definition_id)
        assert response.json()["repair"]["definition_status"] == "superseded"
        assert len(response.json()["requirements"]) == 3


def test_readiness_is_owner_scoped() -> None:
    _, selection, repair_key, _, _, _ = seed_readiness_definition()
    device_id = str(uuid4())

    with TestClient(app) as owner, TestClient(app) as stranger:
        register(owner, "readiness_private_owner")
        register(stranger, "readiness_private_stranger")
        session_id = create_session(owner, create_vehicle(owner, selection), device_id)
        bind(owner, session_id, device_id, repair_key)

        response = stranger.get(f"/api/v1/repair-sessions/{session_id}/readiness")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "REPAIR_SESSION_NOT_FOUND"
