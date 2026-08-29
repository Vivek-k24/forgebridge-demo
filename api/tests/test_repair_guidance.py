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
    ProcedureAction,
    ProcedureActionDependency,
    ProcedureActionEvidence,
    ProcedureActionRequirementUse,
    RepairDefinition,
    RequirementDefinition,
    RequirementUse,
    RequirementUseEvidence,
    UserGarageInventoryItem,
)
from partgraph.repair_session.models import RepairProcedureActionState
from partgraph.vehicle.schemas import VehicleConfigurationInput
from partgraph.vehicle.service import resolve_configuration

DIY_SUPPORTED = UUID("11111111-1111-4111-8111-111111111111")
CSRF = {"X-PartGraph-CSRF": "1"}
PASSWORD = "correct-horse-battery-staple"


def seed_guidance_definition() -> tuple[dict[str, object], str, UUID, UUID, UUID]:
    async def seed() -> tuple[dict[str, object], str, UUID, UUID, UUID]:
        suffix = uuid4().hex[:10]
        repair_key = f"guided-service-{suffix}"
        selection: dict[str, object] = {
            "year": 2020,
            "market": "US",
            "make": "Mazda",
            "model": f"Mazda3-{suffix}",
            "generation": "4",
            "trim": "Preferred",
            "body_style": "Hatchback",
            "engine": "2.5L I4",
            "transmission": "Automatic",
            "drivetrain": "FWD",
        }
        now = datetime.now(UTC)
        async with session_factory() as session:
            configuration, _ = await resolve_configuration(
                session,
                VehicleConfigurationInput.model_validate(selection),
            )
            source = CatalogSource(
                source_key=f"guided-source-{suffix}",
                display_name="Guided repair deterministic fixture",
                source_class="oem_service",
                license_status="approved",
                automation_allowed=False,
            )
            evidence = CatalogVerifiedEvidence(
                staging_record_id=uuid4(),
                candidate_type="repair_guidance",
                verified_payload={"fixture": True},
                vehicle_identity={"configuration_id": str(configuration.id)},
                source_name="guided-fixture",
                source_type="oem_service",
                source_record_id=f"guided-{suffix}",
                source_url="https://example.invalid/guided-fixture",
                raw_sha256="d" * 64,
                fetched_at=now,
                observed_at=now,
                provenance={"section": "guided-fixture"},
                extraction_method="deterministic_fixture",
                promoted_by="test-suite",
            )
            session.add_all([source, evidence])
            await session.flush()

            definition = RepairDefinition(
                vehicle_configuration_id=configuration.id,
                capability_policy_id=DIY_SUPPORTED,
                repair_key=repair_key,
                title="Guided fixture repair",
                version=1,
                status="verified",
                verified_at=now,
            )
            tool = RequirementDefinition(
                requirement_key=f"tool.guided.socket.{suffix}",
                category="tool",
                display_name="Guided fixture socket",
                default_unit="each",
            )
            session.add_all([definition, tool])
            await session.flush()

            requirement_claim = MechanicalClaim(
                source_id=source.id,
                verified_evidence_id=evidence.id,
                vehicle_configuration_id=configuration.id,
                claim_domain="repair_requirement",
                claim_risk="normal",
                normalized_key=f"repair:{repair_key}:tool",
                repair_key=repair_key,
                claim_payload={"tool": "fixture"},
                explicit_claim=True,
                exact_applicability=True,
                promotion_state="verified",
                reviewed_at=now,
                reviewed_by="test-suite",
            )
            procedure_claims = [
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
            session.add_all([requirement_claim, *procedure_claims])
            await session.flush()

            tool_use = RequirementUse(
                repair_definition_id=definition.id,
                operation_id=None,
                requirement_definition_id=tool.id,
                quantity=Decimal("1"),
                unit="each",
                necessity="required",
                fulfillment_mode="reusable",
                timing="whole_repair",
            )
            prepare = ProcedureAction(
                repair_definition_id=definition.id,
                action_key="prepare",
                title="Prepare the work area",
                instruction="Use the verified workspace preparation for this exact repair.",
                position=0,
                skippable=False,
            )
            remove = ProcedureAction(
                repair_definition_id=definition.id,
                action_key="remove-cover",
                title="Remove the service cover",
                instruction="Remove the verified service cover for this exact repair.",
                position=1,
                skippable=False,
            )
            session.add_all([tool_use, prepare, remove])
            await session.flush()
            session.add_all(
                [
                    RequirementUseEvidence(
                        requirement_use_id=tool_use.id,
                        mechanical_claim_id=requirement_claim.id,
                    ),
                    ProcedureActionEvidence(
                        action_id=prepare.id,
                        mechanical_claim_id=procedure_claims[0].id,
                    ),
                    ProcedureActionEvidence(
                        action_id=remove.id,
                        mechanical_claim_id=procedure_claims[1].id,
                    ),
                    ProcedureActionDependency(
                        action_id=remove.id,
                        prerequisite_action_id=prepare.id,
                    ),
                    ProcedureActionRequirementUse(
                        action_id=remove.id,
                        requirement_use_id=tool_use.id,
                    ),
                ]
            )
            await session.commit()
            return selection, repair_key, tool.id, prepare.id, remove.id

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


def create_bound_session(
    client: TestClient,
    *,
    selection: dict[str, object],
    repair_key: str,
    device_id: str,
) -> str:
    vehicle = client.post(
        "/api/v1/user-vehicles/manual",
        json={"nickname": "Guided car", "selection": selection},
        headers=CSRF,
    )
    assert vehicle.status_code == 201, vehicle.text
    repair_session = client.post(
        "/api/v1/repair-sessions",
        json={"user_vehicle_id": vehicle.json()["id"], "title": "Guided repair"},
        headers={
            **CSRF,
            "X-PartGraph-Device-ID": device_id,
            "Idempotency-Key": f"guided_session_{uuid4().hex[:12]}",
        },
    )
    assert repair_session.status_code == 201, repair_session.text
    session_id = repair_session.json()["session"]["id"]
    binding = client.put(
        f"/api/v1/repair-sessions/{session_id}/repair-definition",
        json={"repair_key": repair_key},
        headers={**CSRF, "X-PartGraph-Device-ID": device_id},
    )
    assert binding.status_code == 200, binding.text
    return session_id


def progress_headers(device_id: str, key: str) -> dict[str, str]:
    return {
        **CSRF,
        "X-PartGraph-Device-ID": device_id,
        "Idempotency-Key": key,
    }


def test_guidance_selects_first_action_then_surfaces_inventory_blocker() -> None:
    selection, repair_key, tool_id, prepare_id, remove_id = seed_guidance_definition()
    device_id = str(uuid4())

    with TestClient(app) as client:
        user_id = register(client, "guided_owner")
        session_id = create_bound_session(
            client,
            selection=selection,
            repair_key=repair_key,
            device_id=device_id,
        )

        first = client.get(f"/api/v1/repair-sessions/{session_id}/guidance")
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "action_available"
        assert first.json()["current_action"]["action_key"] == "prepare"
        assert first.json()["current_action"]["inventory_blockers"] == []

        async def complete_prepare() -> None:
            async with session_factory() as session:
                session.add(
                    RepairProcedureActionState(
                        user_id=UUID(user_id),
                        session_id=UUID(session_id),
                        action_id=prepare_id,
                        progress_state="completed",
                    )
                )
                await session.commit()

        asyncio.run(complete_prepare())
        blocked = client.get(f"/api/v1/repair-sessions/{session_id}/guidance")
        assert blocked.status_code == 200, blocked.text
        assert blocked.json()["status"] == "inventory_blocked"
        assert blocked.json()["current_action"]["action_key"] == "remove-cover"
        blocker = blocked.json()["current_action"]["inventory_blockers"][0]
        assert blocker["requirement_definition_id"] == str(tool_id)
        assert blocker["readiness_state"] == "missing"

        async def add_tool() -> None:
            async with session_factory() as session:
                session.add(
                    UserGarageInventoryItem(
                        user_id=UUID(user_id),
                        requirement_definition_id=tool_id,
                        quantity_available=Decimal("1"),
                        unit="each",
                    )
                )
                await session.commit()

        asyncio.run(add_tool())
        ready = client.get(f"/api/v1/repair-sessions/{session_id}/guidance")
        assert ready.status_code == 200, ready.text
        assert ready.json()["status"] == "action_available"
        assert ready.json()["current_action"]["action_id"] == str(remove_id)
        assert ready.json()["current_action"]["inventory_blockers"] == []


def test_guidance_plan_tracks_private_progress_and_completion() -> None:
    selection, repair_key, _, prepare_id, remove_id = seed_guidance_definition()
    device_id = str(uuid4())

    with TestClient(app) as client:
        user_id = register(client, "guided_plan")
        session_id = create_bound_session(
            client,
            selection=selection,
            repair_key=repair_key,
            device_id=device_id,
        )

        async def complete_all() -> None:
            async with session_factory() as session:
                session.add_all(
                    [
                        RepairProcedureActionState(
                            user_id=UUID(user_id),
                            session_id=UUID(session_id),
                            action_id=prepare_id,
                            progress_state="completed",
                        ),
                        RepairProcedureActionState(
                            user_id=UUID(user_id),
                            session_id=UUID(session_id),
                            action_id=remove_id,
                            progress_state="completed",
                        ),
                    ]
                )
                await session.commit()

        asyncio.run(complete_all())
        response = client.get(f"/api/v1/repair-sessions/{session_id}/guidance/plan")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "procedure_complete"
        assert body["procedure_complete"] is True
        assert body["current_action"] is None
        assert body["summary"]["completed"] == 2
        assert [item["progress_state"] for item in body["actions"]] == [
            "completed",
            "completed",
        ]


def test_guidance_is_owner_scoped() -> None:
    selection, repair_key, _, _, _ = seed_guidance_definition()
    device_id = str(uuid4())

    with TestClient(app) as owner, TestClient(app) as stranger:
        register(owner, "guided_private_owner")
        register(stranger, "guided_private_stranger")
        session_id = create_bound_session(
            owner,
            selection=selection,
            repair_key=repair_key,
            device_id=device_id,
        )
        response = stranger.get(f"/api/v1/repair-sessions/{session_id}/guidance")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "REPAIR_SESSION_NOT_FOUND"


def test_action_mutation_is_lease_protected_idempotent_and_deterministic() -> None:
    selection, repair_key, tool_id, prepare_id, remove_id = seed_guidance_definition()
    device_a = str(uuid4())
    device_b = str(uuid4())

    with TestClient(app) as client:
        register(client, "guided_mutation")
        session_id = create_bound_session(
            client,
            selection=selection,
            repair_key=repair_key,
            device_id=device_a,
        )

        wrong_device = client.put(
            f"/api/v1/repair-sessions/{session_id}/guidance/actions/{prepare_id}",
            json={"progress_state": "completed"},
            headers=progress_headers(device_b, "guided_wrong_device"),
        )
        assert wrong_device.status_code == 409
        assert wrong_device.json()["error"]["code"] == "REPAIR_SESSION_LEASE_HELD"

        not_current = client.put(
            f"/api/v1/repair-sessions/{session_id}/guidance/actions/{remove_id}",
            json={"progress_state": "completed"},
            headers=progress_headers(device_a, "guided_not_current"),
        )
        assert not_current.status_code == 409
        assert not_current.json()["error"]["code"] == "REPAIR_PROCEDURE_ACTION_NOT_CURRENT"

        completed = client.put(
            f"/api/v1/repair-sessions/{session_id}/guidance/actions/{prepare_id}",
            json={"progress_state": "completed"},
            headers=progress_headers(device_a, "guided_complete_prepare"),
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["status"] == "inventory_blocked"
        assert completed.json()["current_action"]["action_id"] == str(remove_id)

        replay = client.put(
            f"/api/v1/repair-sessions/{session_id}/guidance/actions/{prepare_id}",
            json={"progress_state": "completed"},
            headers=progress_headers(device_a, "guided_complete_prepare"),
        )
        assert replay.status_code == 200, replay.text

        conflict = client.put(
            f"/api/v1/repair-sessions/{session_id}/guidance/actions/{prepare_id}",
            json={"progress_state": "blocked", "blocker_code": "different"},
            headers=progress_headers(device_a, "guided_complete_prepare"),
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "REPAIR_SESSION_IDEMPOTENCY_CONFLICT"

        inventory_blocked = client.put(
            f"/api/v1/repair-sessions/{session_id}/guidance/actions/{remove_id}",
            json={"progress_state": "completed"},
            headers=progress_headers(device_a, "guided_complete_blocked"),
        )
        assert inventory_blocked.status_code == 409
        assert (
            inventory_blocked.json()["error"]["code"]
            == "REPAIR_PROCEDURE_ACTION_INVENTORY_BLOCKED"
        )

        have_tool = client.put(
            f"/api/v1/repair-sessions/{session_id}/readiness/{tool_id}",
            json={"readiness_state": "have"},
            headers=progress_headers(device_a, "guided_have_tool"),
        )
        assert have_tool.status_code == 200, have_tool.text

        finish = client.put(
            f"/api/v1/repair-sessions/{session_id}/guidance/actions/{remove_id}",
            json={"progress_state": "completed"},
            headers=progress_headers(device_a, "guided_complete_remove"),
        )
        assert finish.status_code == 200, finish.text
        assert finish.json()["status"] == "procedure_complete"
        assert finish.json()["procedure_complete"] is True

        history = client.get(f"/api/v1/repair-sessions/{session_id}/events?limit=100")
        assert history.status_code == 200, history.text
        procedure_events = [
            item
            for item in history.json()["items"]
            if item["event_type"] == "procedure_action_state_changed"
        ]
        assert [item["payload"]["action_id"] for item in procedure_events] == [
            str(prepare_id),
            str(remove_id),
        ]


def test_action_can_be_blocked_then_completed_but_non_skippable_action_cannot_skip() -> None:
    selection, repair_key, _, prepare_id, _ = seed_guidance_definition()
    device_id = str(uuid4())

    with TestClient(app) as client:
        register(client, "guided_blocked")
        session_id = create_bound_session(
            client,
            selection=selection,
            repair_key=repair_key,
            device_id=device_id,
        )

        skipped = client.put(
            f"/api/v1/repair-sessions/{session_id}/guidance/actions/{prepare_id}",
            json={"progress_state": "skipped"},
            headers=progress_headers(device_id, "guided_skip_forbidden"),
        )
        assert skipped.status_code == 409
        assert skipped.json()["error"]["code"] == "REPAIR_PROCEDURE_ACTION_NOT_SKIPPABLE"

        blocked = client.put(
            f"/api/v1/repair-sessions/{session_id}/guidance/actions/{prepare_id}",
            json={
                "progress_state": "blocked",
                "blocker_code": "unexpected_condition",
                "notes": "Need to inspect before continuing.",
            },
            headers=progress_headers(device_id, "guided_mark_blocked"),
        )
        assert blocked.status_code == 200, blocked.text
        assert blocked.json()["status"] == "action_blocked"
        assert blocked.json()["current_action"]["progress_state"] == "blocked"
        assert blocked.json()["current_action"]["blocker_code"] == "unexpected_condition"

        resumed = client.put(
            f"/api/v1/repair-sessions/{session_id}/guidance/actions/{prepare_id}",
            json={"progress_state": "completed"},
            headers=progress_headers(device_id, "guided_resolve_blocked"),
        )
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["current_action"]["action_key"] == "remove-cover"
