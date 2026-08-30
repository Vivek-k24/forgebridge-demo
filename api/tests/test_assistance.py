import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from partgraph.assistance.models import AIInvocation
from partgraph.auth.service import set_user_context
from partgraph.catalog.models import CatalogVerifiedEvidence
from partgraph.catalog.source_models import CatalogSource, MechanicalClaim
from partgraph.database import session_factory
from partgraph.main import app
from partgraph.repair_definition.models import (
    ProcedureAction,
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
CSRF = {"X-PartGraph-CSRF": "1"}
PASSWORD = "correct-horse-battery-staple"


def _register(client: TestClient, prefix: str) -> UUID:
    suffix = uuid4().hex[:10]
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
    return UUID(response.json()["user"]["id"])


def _seed_definition() -> tuple[dict[str, object], str, UUID]:
    async def seed() -> tuple[dict[str, object], str, UUID]:
        suffix = uuid4().hex[:10]
        repair_key = f"assistance-service-{suffix}"
        selection: dict[str, object] = {
            "year": 2021,
            "market": "US",
            "make": "Toyota",
            "model": f"Camry-{suffix}",
            "generation": "8",
            "trim": "SE",
            "body_style": "Sedan",
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
                source_key=f"assistance-source-{suffix}",
                display_name="Assistance deterministic fixture",
                source_class="oem_service",
                license_status="approved",
                automation_allowed=False,
            )
            evidence = CatalogVerifiedEvidence(
                staging_record_id=uuid4(),
                candidate_type="repair_assistance",
                verified_payload={"fixture": True},
                vehicle_identity={"configuration_id": str(configuration.id)},
                source_name="assistance-fixture",
                source_type="oem_service",
                source_record_id=f"assistance-{suffix}",
                source_url="https://example.invalid/assistance-fixture",
                raw_sha256="a" * 64,
                fetched_at=now,
                observed_at=now,
                provenance={"section": "assistance-fixture"},
                extraction_method="deterministic_fixture",
                promoted_by="test-suite",
            )
            session.add_all([source, evidence])
            await session.flush()

            definition = RepairDefinition(
                vehicle_configuration_id=configuration.id,
                capability_policy_id=DIY_SUPPORTED,
                repair_key=repair_key,
                title="Assistance fixture repair",
                version=1,
                status="verified",
                verified_at=now,
            )
            tool = RequirementDefinition(
                requirement_key=f"tool.assistance.fixture.{suffix}",
                category="tool",
                display_name="Assistance fixture tool",
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
                claim_payload={"tool": "synthetic fixture"},
                explicit_claim=True,
                exact_applicability=True,
                promotion_state="verified",
                reviewed_at=now,
                reviewed_by="test-suite",
            )
            procedure_claim = MechanicalClaim(
                source_id=source.id,
                verified_evidence_id=evidence.id,
                vehicle_configuration_id=configuration.id,
                claim_domain="repair_procedure",
                claim_risk="normal",
                normalized_key=f"repair:{repair_key}:service",
                repair_key=repair_key,
                claim_payload={"action": "synthetic fixture"},
                explicit_claim=True,
                exact_applicability=True,
                promotion_state="verified",
                reviewed_at=now,
                reviewed_by="test-suite",
            )
            session.add_all([requirement_claim, procedure_claim])
            await session.flush()

            use = RequirementUse(
                repair_definition_id=definition.id,
                operation_id=None,
                requirement_definition_id=tool.id,
                quantity=Decimal("1"),
                unit="each",
                necessity="required",
                fulfillment_mode="reusable",
                timing="whole_repair",
            )
            action = ProcedureAction(
                repair_definition_id=definition.id,
                action_key="service",
                title="Synthetic verified service action",
                instruction="SYNTHETIC TEST ONLY. No mechanical instruction.",
                position=0,
                skippable=False,
            )
            session.add_all([use, action])
            await session.flush()
            session.add_all(
                [
                    RequirementUseEvidence(
                        requirement_use_id=use.id,
                        mechanical_claim_id=requirement_claim.id,
                    ),
                    ProcedureActionEvidence(
                        action_id=action.id,
                        mechanical_claim_id=procedure_claim.id,
                    ),
                    ProcedureActionRequirementUse(
                        action_id=action.id,
                        requirement_use_id=use.id,
                    ),
                ]
            )
            await session.commit()
            return selection, repair_key, tool.id

    return asyncio.run(seed())


def _bound_session(
    client: TestClient,
    selection: dict[str, object],
    repair_key: str,
    device_id: str,
) -> str:
    vehicle = client.post(
        "/api/v1/user-vehicles/manual",
        json={"nickname": "Assistance car", "selection": selection},
        headers=CSRF,
    )
    assert vehicle.status_code == 201, vehicle.text
    assert vehicle.json()["identity_resolution"] == "matched"
    repair = client.post(
        "/api/v1/repair-sessions",
        json={"user_vehicle_id": vehicle.json()["id"], "title": "Assistance repair"},
        headers={
            **CSRF,
            "X-PartGraph-Device-ID": device_id,
            "Idempotency-Key": f"assistance_session_{uuid4().hex[:10]}",
        },
    )
    assert repair.status_code == 201, repair.text
    session_id = repair.json()["session"]["id"]
    binding = client.put(
        f"/api/v1/repair-sessions/{session_id}/repair-definition",
        json={"repair_key": repair_key},
        headers={**CSRF, "X-PartGraph-Device-ID": device_id},
    )
    assert binding.status_code == 200, binding.text
    return session_id


def _mutation_headers(device_id: str, prefix: str) -> dict[str, str]:
    return {
        **CSRF,
        "X-PartGraph-Device-ID": device_id,
        "Idempotency-Key": f"{prefix}_{uuid4().hex[:10]}",
    }


def test_deterministic_assistance_tracks_guidance_without_ai_invocation() -> None:
    selection, repair_key, requirement_id = _seed_definition()
    device_id = str(uuid4())

    with TestClient(app) as owner, TestClient(app) as stranger:
        _register(owner, "assist_owner")
        _register(stranger, "assist_stranger")
        session_id = _bound_session(owner, selection, repair_key, device_id)

        blocked = owner.get(
            f"/api/v1/repair-sessions/{session_id}/assistance/explanation"
        )
        assert blocked.status_code == 200, blocked.text
        blocked_body = blocked.json()
        assert blocked_body["mode"] == "deterministic"
        assert blocked_body["ai_invoked"] is False
        assert blocked_body["guidance_status"] == "inventory_blocked"
        assert blocked_body["reason_code"] == "current_action_inventory_blocked"
        assert blocked_body["current_action"]["action_key"] == "service"
        assert blocked_body["inventory_blockers"][0]["requirement_definition_id"] == str(
            requirement_id
        )

        ready = owner.put(
            f"/api/v1/repair-sessions/{session_id}/readiness/{requirement_id}",
            json={"readiness_state": "have"},
            headers=_mutation_headers(device_id, "assist_ready"),
        )
        assert ready.status_code == 200, ready.text

        available = owner.get(
            f"/api/v1/repair-sessions/{session_id}/assistance/explanation"
        )
        assert available.status_code == 200, available.text
        available_body = available.json()
        assert available_body["guidance_status"] == "action_available"
        assert available_body["reason_code"] == "next_verified_action"
        assert "No AI model was needed" in available_body["explanation"]
        action_id = available_body["current_action"]["action_id"]

        physically_blocked = owner.put(
            f"/api/v1/repair-sessions/{session_id}/guidance/actions/{action_id}",
            json={"progress_state": "blocked", "blocker_code": "fixture_problem"},
            headers=_mutation_headers(device_id, "assist_blocked"),
        )
        assert physically_blocked.status_code == 200, physically_blocked.text
        blocked_explanation = owner.get(
            f"/api/v1/repair-sessions/{session_id}/assistance/explanation"
        )
        assert blocked_explanation.status_code == 200, blocked_explanation.text
        assert blocked_explanation.json()["reason_code"] == "current_action_physically_blocked"

        complete = owner.put(
            f"/api/v1/repair-sessions/{session_id}/guidance/actions/{action_id}",
            json={"progress_state": "completed"},
            headers=_mutation_headers(device_id, "assist_complete"),
        )
        assert complete.status_code == 200, complete.text
        final = owner.get(f"/api/v1/repair-sessions/{session_id}/assistance/explanation")
        assert final.status_code == 200, final.text
        final_body = final.json()
        assert final_body["guidance_status"] == "procedure_complete"
        assert final_body["reason_code"] == "verified_procedure_complete"
        assert final_body["current_action"] is None

        isolated = stranger.get(
            f"/api/v1/repair-sessions/{session_id}/assistance/explanation"
        )
        assert isolated.status_code == 404
        assert isolated.json()["error"]["code"] == "REPAIR_SESSION_NOT_FOUND"

    async def no_ai_rows() -> None:
        async with session_factory() as session:
            count = await session.scalar(
                select(func.count()).select_from(AIInvocation).where(
                    AIInvocation.session_id == UUID(session_id)
                )
            )
            assert count == 0

    asyncio.run(no_ai_rows())


def test_ai_invocation_audit_is_owner_scoped_by_rls() -> None:
    with TestClient(app) as client_a, TestClient(app) as client_b:
        user_a = _register(client_a, "audit_a")
        user_b = _register(client_b, "audit_b")

    invocation_id = uuid4()

    async def scenario() -> None:
        async with session_factory() as session:
            async with session.begin():
                session.add(
                    AIInvocation(
                        id=invocation_id,
                        user_id=user_a,
                        purpose="explain_verified_state",
                        reason_code="future_ambiguous_request",
                        provider="synthetic-test-provider",
                        model="synthetic-test-model",
                        prompt_template_key="assistance.explain",
                        prompt_version="test-v1",
                        prompt_sha256="b" * 64,
                        status="succeeded",
                        latency_ms=12,
                        input_tokens=10,
                        output_tokens=5,
                        cost_microusd=0,
                        confidence=Decimal("0.9000"),
                        result_metadata={"synthetic": True},
                        completed_at=datetime.now(UTC),
                    )
                )

        async with session_factory() as session:
            async with session.begin():
                await session.execute(text("SET LOCAL ROLE partgraph_app"))
                await set_user_context(session, user_b)
                assert await session.get(AIInvocation, invocation_id) is None

        async with session_factory() as session:
            async with session.begin():
                await session.execute(text("SET LOCAL ROLE partgraph_app"))
                await set_user_context(session, user_a)
                own = await session.get(AIInvocation, invocation_id)
                assert own is not None
                assert own.prompt_template_key == "assistance.explain"
                assert own.cost_microusd == 0

    asyncio.run(scenario())
