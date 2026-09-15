import hashlib
import json
import os
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select, text

from partgraph.database import session_factory
from partgraph.errors import PartGraphError
from partgraph.identity.auth.models import User
from partgraph.identity.auth.service import set_user_context
from partgraph.identity.user_vehicle.models import UserVehicle
from partgraph.identity.vehicle.models import VehicleConfiguration
from partgraph.knowledge.models import (
    CatalogSource,
    CatalogVerifiedEvidence,
    MechanicalClaim,
    RepairDefinition,
)
from partgraph.knowledge.repair_materialization_contract import (
    RepairDefinitionMaterializationCreate,
)
from partgraph.knowledge.repair_materialization_service import (
    materialize_repair_definition_service,
)
from partgraph.repair_experience.completion import _completion_view
from partgraph.repair_experience.guidance import (
    GuidanceActionUpdate,
    _guidance_view,
    update_action_progress,
)
from partgraph.repair_experience.readiness import (
    RepairReadinessUpdate,
    _readiness_view,
    update_repair_readiness,
)
from partgraph.repair_experience.reorientation import build_reorientation
from partgraph.repair_experience.repair_definition_binding import (
    RepairDefinitionBind,
    bind_repair_definition,
)
from partgraph.repair_experience.service import (
    append_status_event,
    create_repair_session,
    event_history,
    resume_repair_session,
)

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
REFERENCE_VEHICLE_ID = UUID("7feb13e9-bca0-5d8b-b701-f0260cce5da1")
REFERENCE_REPAIR_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "reference"
    / "2009_honda_civic_hybrid_repairs_v1"
    / "engine_oil_filter_change.json"
)


def _claim_payload(item: dict[str, object], *, requirement: bool) -> dict[str, object]:
    excluded = {"source_pages", "use_key"} if requirement else {"source_pages"}
    return {key: value for key, value in item.items() if key not in excluded}


def _raw_sha(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class ReferenceRepairRuntimeDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        self.reference = json.loads(REFERENCE_REPAIR_PATH.read_text(encoding="utf-8"))
        self.assertEqual(self.reference["vehicle_configuration_id"], str(REFERENCE_VEHICLE_ID))
        self.assertEqual(self.reference["repair_key"], "engine-oil-filter-change")
        self.assertEqual(len(self.reference["requirements"]), 8)
        self.assertEqual(len(self.reference["actions"]), 6)

        self.db = session_factory()
        self.transaction = await self.db.begin()

        vehicle = await self.db.get(VehicleConfiguration, REFERENCE_VEHICLE_ID)
        self.assertIsNotNone(vehicle)
        assert vehicle is not None
        self.assertEqual((vehicle.year, vehicle.make, vehicle.model), (2009, "Honda", "Civic"))
        self.assertEqual(vehicle.verification_status, "verified")

        current = await self.db.scalar(
            select(RepairDefinition).where(
                RepairDefinition.vehicle_configuration_id == REFERENCE_VEHICLE_ID,
                RepairDefinition.repair_key == self.reference["repair_key"],
                RepairDefinition.status == "verified",
            )
        )
        if current is not None:
            await self.transaction.rollback()
            await self.db.close()
            raise unittest.SkipTest(
                "Reference repair already exists in this database; runtime CI expects a fresh migrated database."
            )

        suffix = uuid4().hex[:12]
        now = datetime.now(UTC)
        source = CatalogSource(
            id=uuid4(),
            source_key=f"reference-runtime-{suffix}",
            display_name="Reference runtime OEM service fixture",
            source_class="oem_service",
            license_status="approved",
            automation_allowed=False,
        )
        self.db.add(source)

        self.user = User(
            id=uuid4(),
            email=f"reference-runtime-{suffix}@example.invalid",
            username=f"runtime_{suffix}",
            password_hash="reference-runtime-fixture",
            role="owner",
            is_active=True,
        )
        self.user_vehicle = UserVehicle(
            id=uuid4(),
            user_id=self.user.id,
            canonical_configuration_id=REFERENCE_VEHICLE_ID,
            nickname="Reference Civic Hybrid",
            identity_source="manual",
            identity_resolution="exact",
            identity_snapshot={
                "year": 2009,
                "market": "US",
                "make": "Honda",
                "model": "Civic",
                "trim": "Hybrid",
            },
        )
        self.db.add_all([self.user, self.user_vehicle])
        await self.db.flush()

        requirement_claim_ids: dict[str, UUID] = {}
        action_claim_ids: dict[str, UUID] = {}
        for claim_domain, key_name, requirement, items, target in (
            (
                "repair_requirement",
                "use_key",
                True,
                self.reference["requirements"],
                requirement_claim_ids,
            ),
            (
                "repair_procedure",
                "action_key",
                False,
                self.reference["actions"],
                action_claim_ids,
            ),
        ):
            for item in items:
                item_key = str(item[key_name])
                payload = _claim_payload(item, requirement=requirement)
                evidence = CatalogVerifiedEvidence(
                    id=uuid4(),
                    staging_record_id=uuid4(),
                    candidate_type="mechanical_claim_candidate",
                    verified_payload={"mechanical_claim": payload},
                    vehicle_identity={"vehicle_configuration_id": str(REFERENCE_VEHICLE_ID)},
                    source_name=source.source_key,
                    source_type="oem_service",
                    source_record_id=f"reference-runtime:{claim_domain}:{item_key}",
                    source_url=f"https://example.invalid/reference-runtime/{claim_domain}/{item_key}",
                    raw_sha256=_raw_sha(payload),
                    fetched_at=now,
                    provenance={
                        "fixture": "reference-repair-runtime",
                        "source_pages": item.get("source_pages", []),
                    },
                    extraction_method="reference_fixture",
                    promoted_by="reference-runtime-reviewer",
                )
                claim = MechanicalClaim(
                    id=uuid4(),
                    source_id=source.id,
                    verified_evidence_id=evidence.id,
                    vehicle_configuration_id=REFERENCE_VEHICLE_ID,
                    claim_domain=claim_domain,
                    claim_risk="normal",
                    normalized_key=f"reference.runtime.{claim_domain}.{item_key}",
                    repair_key=self.reference["repair_key"],
                    claim_payload=payload,
                    explicit_claim=True,
                    exact_applicability=True,
                    promotion_state="verified",
                    reviewed_at=now,
                    reviewed_by="reference-runtime-curator",
                )
                self.db.add_all([evidence, claim])
                target[item_key] = claim.id
        await self.db.flush()

        request = RepairDefinitionMaterializationCreate(
            vehicle_configuration_id=REFERENCE_VEHICLE_ID,
            repair_key=self.reference["repair_key"],
            title=self.reference["title"],
            capability_policy_key=self.reference["capability_policy_key"],
            operations=self.reference["operations"],
            requirements=[
                {
                    **{key: value for key, value in item.items() if key != "source_pages"},
                    "supporting_claim_ids": [requirement_claim_ids[str(item["use_key"])]],
                }
                for item in self.reference["requirements"]
            ],
            actions=[
                {
                    **{key: value for key, value in item.items() if key != "source_pages"},
                    "supporting_claim_ids": [action_claim_ids[str(item["action_key"])]],
                }
                for item in self.reference["actions"]
            ],
        )

        await self.db.execute(text("SET LOCAL ROLE partgraph_materializer"))
        publication = await materialize_repair_definition_service(
            self.db,
            request=request,
            actor="reference-runtime-curator",
            idempotency_key=f"reference-runtime:{suffix}",
        )
        self.repair_definition_id = publication.repair_definition_id

        await self.db.execute(text("SET LOCAL ROLE partgraph_app"))
        await set_user_context(self.db, self.user.id)
        self.device_id = uuid4()

    async def asyncTearDown(self) -> None:
        if hasattr(self, "transaction") and self.transaction.is_active:
            await self.transaction.rollback()
        if hasattr(self, "db"):
            await self.db.close()

    async def test_reference_oil_change_runs_readiness_pause_resume_and_completion(self) -> None:
        bundle = await create_repair_session(
            self.db,
            user_id=self.user.id,
            user_vehicle_id=self.user_vehicle.id,
            title="Engine oil and filter change",
            device_id=self.device_id,
            idempotency_key="reference_runtime_session",
        )
        session_id = bundle.repair_session.id

        binding = await bind_repair_definition(
            session_id,
            RepairDefinitionBind(repair_key="engine-oil-filter-change"),
            self.user,
            self.db,
            device_header=str(self.device_id),
        )
        self.assertEqual(binding.binding_state, "bound")
        self.assertEqual(binding.repair_definition_id, self.repair_definition_id)
        self.assertEqual(binding.vehicle_configuration_id, REFERENCE_VEHICLE_ID)

        readiness = await _readiness_view(
            self.db,
            user_id=self.user.id,
            repair_session=bundle.repair_session,
        )
        self.assertEqual(readiness.summary.total, 8)
        self.assertEqual(readiness.summary.blocked, 7)
        self.assertEqual(readiness.summary.missing, 8)

        guidance = await _guidance_view(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
            include_plan=False,
        )
        self.assertEqual(guidance.status, "inventory_blocked")
        self.assertIsNotNone(guidance.current_action)
        assert guidance.current_action is not None
        self.assertEqual(guidance.current_action.action_key, "prepare-access")
        self.assertEqual(
            {item.requirement_key for item in guidance.current_action.inventory_blockers},
            {"tool.flat_tip_screwdriver", "workspace.safe_underbody_access"},
        )

        with self.assertRaises(PartGraphError) as blocked:
            await update_action_progress(
                session_id,
                guidance.current_action.action_id,
                GuidanceActionUpdate(progress_state="completed"),
                self.user,
                self.db,
                device_header=str(self.device_id),
                idempotency_header="blocked_action_attempt",
            )
        self.assertEqual(blocked.exception.code, "REPAIR_PROCEDURE_ACTION_INVENTORY_BLOCKED")

        required_items = [item for item in readiness.requirements if item.necessity == "required"]
        self.assertEqual(len(required_items), 7)
        for index, item in enumerate(required_items, start=1):
            readiness = await update_repair_readiness(
                session_id,
                item.requirement_definition_id,
                RepairReadinessUpdate(readiness_state="have"),
                self.user,
                self.db,
                device_header=str(self.device_id),
                idempotency_header=f"ready_item_{index:02d}",
            )

        self.assertEqual(readiness.summary.blocked, 0)
        self.assertEqual(readiness.summary.ready, 7)
        self.assertEqual(readiness.summary.missing, 1)
        recommended = [item for item in readiness.requirements if item.necessity == "recommended"]
        self.assertEqual(len(recommended), 1)
        self.assertEqual(recommended[0].requirement_key, "equipment.sealed_used_oil_container")
        self.assertEqual(recommended[0].readiness_state, "missing")

        completed_keys: list[str] = []
        for index in range(2):
            guidance = await _guidance_view(
                self.db,
                user_id=self.user.id,
                session_id=session_id,
                include_plan=False,
            )
            self.assertEqual(guidance.status, "action_available")
            assert guidance.current_action is not None
            completed_keys.append(guidance.current_action.action_key)
            await update_action_progress(
                session_id,
                guidance.current_action.action_id,
                GuidanceActionUpdate(progress_state="completed"),
                self.user,
                self.db,
                device_header=str(self.device_id),
                idempotency_header=f"action_done_{index + 1:02d}",
            )

        self.assertEqual(completed_keys, ["prepare-access", "drain-engine-oil"])

        paused = await append_status_event(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
            device_id=self.device_id,
            idempotency_key="reference_runtime_pause",
            event_type="session_paused",
        )
        self.assertEqual(paused.session.status, "paused")

        paused_snapshot = await resume_repair_session(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
            device_id=self.device_id,
        )
        paused_reorientation = await build_reorientation(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
            last_event=paused_snapshot.last_event,
        )
        self.assertEqual(paused_snapshot.session.status, "paused")
        self.assertEqual(paused_reorientation.counts.verified_readiness_blockers, 0)
        self.assertEqual(paused_reorientation.next_verified_action.status, "available")
        self.assertEqual(paused_reorientation.next_verified_action.label, "Replace the oil filter")
        self.assertEqual(paused_reorientation.checkpoint.event_type, "procedure_action_state_changed")
        self.assertIn("drain engine oil", paused_reorientation.checkpoint.label)
        self.assertTrue(
            any(item.event_type == "session_paused" for item in paused_reorientation.recent_activity)
        )

        resumed = await append_status_event(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
            device_id=self.device_id,
            idempotency_key="reference_runtime_resume",
            event_type="session_resumed",
        )
        self.assertEqual(resumed.session.status, "active")

        resumed_snapshot = await resume_repair_session(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
            device_id=self.device_id,
        )
        resumed_reorientation = await build_reorientation(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
            last_event=resumed_snapshot.last_event,
        )
        self.assertEqual(resumed_reorientation.next_verified_action.label, "Replace the oil filter")
        self.assertEqual(resumed_reorientation.counts.verified_readiness_blockers, 0)

        for index in range(2, 6):
            guidance = await _guidance_view(
                self.db,
                user_id=self.user.id,
                session_id=session_id,
                include_plan=False,
            )
            self.assertEqual(guidance.status, "action_available")
            assert guidance.current_action is not None
            completed_keys.append(guidance.current_action.action_key)
            await update_action_progress(
                session_id,
                guidance.current_action.action_id,
                GuidanceActionUpdate(progress_state="completed"),
                self.user,
                self.db,
                device_header=str(self.device_id),
                idempotency_header=f"action_done_{index + 1:02d}",
            )

        self.assertEqual(
            completed_keys,
            [
                "prepare-access",
                "drain-engine-oil",
                "replace-oil-filter",
                "close-and-refill",
                "verify-finish",
                "reset-oil-life",
            ],
        )

        final_guidance = await _guidance_view(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
            include_plan=False,
        )
        self.assertTrue(final_guidance.procedure_complete)
        self.assertEqual(final_guidance.status, "procedure_complete")
        self.assertIsNone(final_guidance.current_action)
        self.assertEqual(final_guidance.summary.completed, 6)
        self.assertEqual(final_guidance.summary.pending, 0)

        completion = await _completion_view(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
        )
        self.assertEqual(completion.completion_status, "fully_mechanically_complete")
        self.assertTrue(completion.supported_partgraph_work_complete)
        self.assertTrue(completion.fully_mechanically_complete)
        self.assertFalse(completion.downstream_required_pending)
        self.assertFalse(completion.unsupported_or_professional_downstream_pending)
        self.assertEqual(completion.downstream_total, 0)
        self.assertEqual(completion.unsupported_action_titles, [])

        history = await event_history(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
            after_sequence=0,
            limit=100,
        )
        self.assertIsNone(history.next_after_sequence)
        self.assertEqual(sum(item.event_type == "readiness_state_changed" for item in history.items), 7)
        self.assertEqual(
            sum(item.event_type == "procedure_action_state_changed" for item in history.items),
            6,
        )
        self.assertEqual(sum(item.event_type == "session_paused" for item in history.items), 1)
        self.assertEqual(sum(item.event_type == "session_resumed" for item in history.items), 1)
        self.assertEqual(history.items[-1].payload["action_key"], "reset-oil-life")
        self.assertEqual(history.items[-1].payload["progress_state"], "completed")


if __name__ == "__main__":
    unittest.main()
