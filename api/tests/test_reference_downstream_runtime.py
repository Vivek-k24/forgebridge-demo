import hashlib
import json
import os
import unittest
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, text

from partgraph.database import session_factory
from partgraph.errors import PartGraphError
from partgraph.identity.auth.models import User
from partgraph.identity.auth.service import set_user_context
from partgraph.identity.user_vehicle.models import UserVehicle
from partgraph.identity.vehicle.models import VehicleConfiguration
from partgraph.knowledge.downstream_materialization import (
    DownstreamRequirementMaterializationCreate,
    materialize_downstream_requirement_service,
)
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
from partgraph.repair_experience.completion import (
    DownstreamRequirementResolution,
    _completion_view,
    satisfy_downstream_requirement,
    start_supported_downstream_repair,
)
from partgraph.repair_experience.guidance import (
    GuidanceActionUpdate,
    _guidance_view,
    update_action_progress,
)
from partgraph.repair_experience.models import RepairSession
from partgraph.repair_experience.readiness import (
    RepairReadinessUpdate,
    _readiness_view,
    update_repair_readiness,
)
from partgraph.repair_experience.repair_definition_binding import (
    RepairDefinitionBind,
    bind_repair_definition,
)
from partgraph.repair_experience.service import create_repair_session
from reference_fixture_support import (
    primary_repair,
    primary_vehicle_id,
    primary_vehicle_snapshot,
)

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
REFERENCE_VEHICLE_ID = primary_vehicle_id()
REFERENCE_VEHICLE = primary_vehicle_snapshot()


def _claim_payload(item: dict[str, object], *, requirement: bool) -> dict[str, object]:
    excluded = {"source_pages", "use_key"} if requirement else {"source_pages"}
    return {key: value for key, value in item.items() if key not in excluded}


def _raw_sha(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class ReferenceDownstreamRuntimeDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def _cleanup_db(self) -> None:
        if hasattr(self, "transaction") and self.transaction.is_active:
            await self.transaction.rollback()
        if hasattr(self, "db"):
            await self.db.close()

    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        _, self.water_pump = primary_repair("engine-water-pump-replacement")
        _, self.coolant_bleed = primary_repair("cooling-system-refill-air-bleed")
        self.assertEqual(
            self.water_pump["vehicle_configuration_id"], str(REFERENCE_VEHICLE_ID)
        )
        self.assertEqual(
            self.coolant_bleed["vehicle_configuration_id"], str(REFERENCE_VEHICLE_ID)
        )
        self.assertEqual(self.water_pump["repair_key"], "engine-water-pump-replacement")
        self.assertEqual(
            self.coolant_bleed["repair_key"], "cooling-system-refill-air-bleed"
        )

        self.db = session_factory()
        self.transaction = await self.db.begin()
        self.addAsyncCleanup(self._cleanup_db)

        vehicle = await self.db.get(VehicleConfiguration, REFERENCE_VEHICLE_ID)
        self.assertIsNotNone(vehicle)
        assert vehicle is not None
        self.assertEqual(
            (vehicle.year, vehicle.make, vehicle.model),
            (
                REFERENCE_VEHICLE["year"],
                REFERENCE_VEHICLE["make"],
                REFERENCE_VEHICLE["model"],
            ),
        )
        self.assertEqual(vehicle.verification_status, "verified")

        for reference in (self.water_pump, self.coolant_bleed):
            current = await self.db.scalar(
                select(RepairDefinition).where(
                    RepairDefinition.vehicle_configuration_id == REFERENCE_VEHICLE_ID,
                    RepairDefinition.repair_key == reference["repair_key"],
                    RepairDefinition.status == "verified",
                )
            )
            if current is not None:
                raise unittest.SkipTest(
                    "Reference downstream repairs already exist; runtime CI expects a fresh migrated database."
                )

        suffix = uuid4().hex[:12]
        now = datetime.now(UTC)
        source = CatalogSource(
            id=uuid4(),
            source_key=f"reference-downstream-{suffix}",
            display_name="Project-owner-reviewed service-manual fixture",
            source_class="licensed_oem_derived",
            license_status="approved",
            automation_allowed=False,
        )
        self.user = User(
            id=uuid4(),
            email=f"reference-downstream-{suffix}@example.invalid",
            username=f"downstream_{suffix}",
            password_hash="reference-downstream-fixture",
            role="owner",
            is_active=True,
        )
        self.user_vehicle = UserVehicle(
            id=uuid4(),
            user_id=self.user.id,
            canonical_configuration_id=REFERENCE_VEHICLE_ID,
            nickname="Reference vehicle",
            identity_source="manual",
            identity_resolution="matched",
            identity_snapshot=dict(REFERENCE_VEHICLE),
        )
        self.db.add_all([source, self.user, self.user_vehicle])
        await self.db.flush()

        requests: dict[str, RepairDefinitionMaterializationCreate] = {}
        action_claim_ids: dict[str, dict[str, UUID]] = {}
        for reference in (self.coolant_bleed, self.water_pump):
            requirement_claim_ids: dict[str, UUID] = {}
            repair_action_claim_ids: dict[str, UUID] = {}
            for claim_domain, key_name, requirement, items, target in (
                (
                    "repair_requirement",
                    "use_key",
                    True,
                    reference["requirements"],
                    requirement_claim_ids,
                ),
                (
                    "repair_procedure",
                    "action_key",
                    False,
                    reference["actions"],
                    repair_action_claim_ids,
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
                        vehicle_identity={
                            "vehicle_configuration_id": str(REFERENCE_VEHICLE_ID)
                        },
                        source_name=source.source_key,
                        source_type="licensed_oem_derived",
                        source_record_id=(
                            f"reference-downstream:{reference['repair_key']}:"
                            f"{claim_domain}:{item_key}"
                        ),
                        source_url=(
                            "https://example.invalid/reference-downstream/"
                            f"{reference['repair_key']}/{claim_domain}/{item_key}"
                        ),
                        raw_sha256=_raw_sha(payload),
                        fetched_at=now,
                        provenance={
                            "fixture": "reference-downstream-runtime",
                            "project_owner_reviewed_on": "2026-09-15",
                            "automation_allowed": False,
                        },
                        extraction_method="reference_fixture",
                        promoted_by="reference-downstream-reviewer",
                    )
                    claim = MechanicalClaim(
                        id=uuid4(),
                        source_id=source.id,
                        verified_evidence_id=evidence.id,
                        vehicle_configuration_id=REFERENCE_VEHICLE_ID,
                        claim_domain=claim_domain,
                        claim_risk="normal",
                        normalized_key=(
                            f"reference.downstream.{reference['repair_key']}."
                            f"{claim_domain}.{item_key}"
                        ),
                        repair_key=reference["repair_key"],
                        claim_payload=payload,
                        explicit_claim=True,
                        exact_applicability=True,
                        promotion_state="verified",
                        reviewed_at=now,
                        reviewed_by="reference-downstream-curator",
                    )
                    self.db.add_all([evidence, claim])
                    target[item_key] = claim.id
            action_claim_ids[reference["repair_key"]] = repair_action_claim_ids
            await self.db.flush()

            requests[reference["repair_key"]] = RepairDefinitionMaterializationCreate(
                vehicle_configuration_id=REFERENCE_VEHICLE_ID,
                repair_key=reference["repair_key"],
                title=reference["title"],
                capability_policy_key=reference["capability_policy_key"],
                operations=reference["operations"],
                requirements=[
                    {
                        **{
                            key: value
                            for key, value in item.items()
                            if key != "source_pages"
                        },
                        "supporting_claim_ids": [
                            requirement_claim_ids[str(item["use_key"])]
                        ],
                    }
                    for item in reference["requirements"]
                ],
                actions=[
                    {
                        **{
                            key: value
                            for key, value in item.items()
                            if key != "source_pages"
                        },
                        "supporting_claim_ids": [
                            repair_action_claim_ids[str(item["action_key"])]
                        ],
                    }
                    for item in reference["actions"]
                ],
            )

        await self.db.execute(text("SET LOCAL ROLE partgraph_materializer"))
        self.definition_ids: dict[str, UUID] = {}
        for reference in (self.coolant_bleed, self.water_pump):
            publication = await materialize_repair_definition_service(
                self.db,
                request=requests[reference["repair_key"]],
                actor="reference-downstream-curator",
                idempotency_key=f"reference-downstream:{reference['repair_key']}:{suffix}",
            )
            self.definition_ids[reference["repair_key"]] = publication.repair_definition_id

        install_action = next(
            item
            for item in self.water_pump["actions"]
            if item["action_key"] == "install-water-pump"
        )
        downstream = await materialize_downstream_requirement_service(
            self.db,
            request=DownstreamRequirementMaterializationCreate(
                source_repair_definition_id=self.definition_ids[
                    "engine-water-pump-replacement"
                ],
                requirement_key=install_action["downstream_requirement_key"],
                title=install_action["downstream_title"],
                detail=install_action["downstream_detail"],
                trigger_type=install_action["downstream_trigger_type"],
                trigger_action_key=install_action["downstream_trigger_action_key"],
                support_state=install_action["downstream_support_state"],
                target_repair_definition_id=self.definition_ids[
                    install_action["downstream_target_repair_key"]
                ],
                milestone_type=install_action["milestone_type"],
                position=0,
                supporting_claim_ids=[
                    action_claim_ids["engine-water-pump-replacement"][
                        "install-water-pump"
                    ]
                ],
            ),
        )
        self.downstream_requirement_id = downstream.downstream_requirement_id

        await self.db.execute(text("RESET ROLE"))
        await self.db.execute(text("SET LOCAL ROLE partgraph_app"))
        await set_user_context(self.db, self.user.id)
        self.device_id = uuid4()

    async def _mark_required_ready(self, repair_session: RepairSession, prefix: str) -> None:
        readiness = await _readiness_view(
            self.db,
            user_id=self.user.id,
            repair_session=repair_session,
        )
        required = [item for item in readiness.requirements if item.necessity == "required"]
        self.assertEqual(len(required), readiness.summary.blocked)
        for index, item in enumerate(required, start=1):
            readiness = await update_repair_readiness(
                repair_session.id,
                item.requirement_definition_id,
                RepairReadinessUpdate(readiness_state="have"),
                self.user,
                self.db,
                device_header=str(self.device_id),
                idempotency_header=f"{prefix}_ready_{index:02d}",
            )
        self.assertEqual(readiness.summary.blocked, 0)

    async def _complete_all_actions(
        self,
        *,
        session_id: UUID,
        prefix: str,
    ) -> list[str]:
        completed: list[str] = []
        index = 1
        while True:
            guidance = await _guidance_view(
                self.db,
                user_id=self.user.id,
                session_id=session_id,
                include_plan=False,
            )
            if guidance.procedure_complete:
                return completed
            self.assertEqual(guidance.status, "action_available")
            self.assertIsNotNone(guidance.current_action)
            assert guidance.current_action is not None
            completed.append(guidance.current_action.action_key)
            await update_action_progress(
                session_id,
                guidance.current_action.action_id,
                GuidanceActionUpdate(progress_state="completed"),
                self.user,
                self.db,
                device_header=str(self.device_id),
                idempotency_header=f"{prefix}_action_{index:02d}",
            )
            index += 1

    async def test_water_pump_stays_incomplete_until_linked_refill_bleed_finishes(self) -> None:
        bundle = await create_repair_session(
            self.db,
            user_id=self.user.id,
            user_vehicle_id=self.user_vehicle.id,
            title=self.water_pump["title"],
            device_id=self.device_id,
            idempotency_key="reference_downstream_source_session",
        )
        source_session_id = bundle.repair_session.id
        binding = await bind_repair_definition(
            source_session_id,
            RepairDefinitionBind(repair_key=self.water_pump["repair_key"]),
            self.user,
            self.db,
            device_header=str(self.device_id),
        )
        self.assertEqual(binding.binding_state, "bound")
        self.assertEqual(
            binding.repair_definition_id,
            self.definition_ids["engine-water-pump-replacement"],
        )

        await self._mark_required_ready(bundle.repair_session, "source")
        completed_source = await self._complete_all_actions(
            session_id=source_session_id,
            prefix="source",
        )
        self.assertEqual(
            completed_source,
            [
                "drain-engine-coolant",
                "remove-access-and-drive-parts",
                "remove-water-pump",
                "install-water-pump",
            ],
        )

        source_completion = await _completion_view(
            self.db,
            user_id=self.user.id,
            session_id=source_session_id,
        )
        self.assertEqual(source_completion.completion_status, "downstream_required_pending")
        self.assertTrue(source_completion.physical_replacement_expected)
        self.assertTrue(source_completion.physical_replacement_performed)
        self.assertTrue(source_completion.supported_partgraph_work_complete)
        self.assertTrue(source_completion.downstream_required_pending)
        self.assertFalse(source_completion.fully_mechanically_complete)
        self.assertEqual(source_completion.downstream_total, 1)
        self.assertEqual(source_completion.downstream_pending, 1)
        self.assertEqual(source_completion.downstream_satisfied, 0)
        downstream = source_completion.downstream_requirements[0]
        self.assertEqual(downstream.requirement_id, self.downstream_requirement_id)
        self.assertEqual(
            downstream.requirement_key,
            "cooling.refill-air-bleed-after-water-pump",
        )
        self.assertEqual(downstream.state, "pending")
        self.assertEqual(downstream.support_state, "supported")
        self.assertEqual(
            downstream.target_repair_key,
            "cooling-system-refill-air-bleed",
        )

        source_completion = await start_supported_downstream_repair(
            source_session_id,
            downstream.requirement_id,
            self.user,
            self.db,
            device_header=str(self.device_id),
        )
        linked_id = source_completion.downstream_requirements[0].resolution_session_id
        self.assertIsNotNone(linked_id)
        assert linked_id is not None

        with self.assertRaises(PartGraphError) as premature:
            await satisfy_downstream_requirement(
                source_session_id,
                downstream.requirement_id,
                DownstreamRequirementResolution(
                    resolution_kind="linked_session_complete"
                ),
                self.user,
                self.db,
                device_header=str(self.device_id),
            )
        self.assertEqual(premature.exception.code, "REQUEST_CONFLICT")

        linked_session = await self.db.get(RepairSession, linked_id)
        self.assertIsNotNone(linked_session)
        assert linked_session is not None
        self.assertEqual(
            linked_session.repair_definition_id,
            self.definition_ids["cooling-system-refill-air-bleed"],
        )
        await self._mark_required_ready(linked_session, "downstream")
        completed_downstream = await self._complete_all_actions(
            session_id=linked_id,
            prefix="downstream",
        )
        self.assertEqual(
            completed_downstream,
            [
                "open-bleed-and-refill",
                "fill-radiator-and-reservoir",
                "warm-and-purge-air",
                "recheck-level-and-leaks",
            ],
        )

        linked_completion = await _completion_view(
            self.db,
            user_id=self.user.id,
            session_id=linked_id,
        )
        self.assertEqual(
            linked_completion.completion_status,
            "fully_mechanically_complete",
        )
        self.assertTrue(linked_completion.fully_mechanically_complete)

        before_resolution = await _completion_view(
            self.db,
            user_id=self.user.id,
            session_id=source_session_id,
        )
        self.assertEqual(before_resolution.completion_status, "downstream_required_pending")
        self.assertFalse(before_resolution.fully_mechanically_complete)

        resolved = await satisfy_downstream_requirement(
            source_session_id,
            downstream.requirement_id,
            DownstreamRequirementResolution(resolution_kind="linked_session_complete"),
            self.user,
            self.db,
            device_header=str(self.device_id),
        )
        self.assertEqual(resolved.completion_status, "fully_mechanically_complete")
        self.assertTrue(resolved.fully_mechanically_complete)
        self.assertFalse(resolved.downstream_required_pending)
        self.assertEqual(resolved.downstream_total, 1)
        self.assertEqual(resolved.downstream_pending, 0)
        self.assertEqual(resolved.downstream_satisfied, 1)
        self.assertEqual(resolved.downstream_requirements[0].state, "satisfied")
        self.assertEqual(
            resolved.downstream_requirements[0].resolution_kind,
            "linked_session_complete",
        )
        self.assertEqual(
            resolved.downstream_requirements[0].resolution_session_id,
            linked_id,
        )


if __name__ == "__main__":
    unittest.main()
