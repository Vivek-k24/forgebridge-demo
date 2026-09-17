import hashlib
import json
import os
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select, text

from partgraph.database import session_factory
from partgraph.identity.auth.models import User
from partgraph.identity.auth.service import set_user_context
from partgraph.identity.user_vehicle.models import UserVehicle
from partgraph.identity.vehicle.models import VehicleConfiguration
from partgraph.identity.vehicle.schemas import VehicleConfigurationInput
from partgraph.identity.vehicle.service import resolve_configuration
from partgraph.knowledge.canonical_claim_materialization import (
    materialize_verified_mechanical_claim_service,
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
from partgraph.repair_experience.repair_definition_binding import (
    RepairDefinitionBind,
    bind_repair_definition,
)
from partgraph.repair_experience.service import create_repair_session, event_history

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
REFERENCE_ROOT = Path(__file__).resolve().parents[1] / "data" / "reference"
FLEET_INDEX_PATH = REFERENCE_ROOT / "phase8_reference_fleet_v1.json"
OPTIONAL_IDENTITY_FIELDS = (
    "generation",
    "trim",
    "body_style",
    "engine",
    "transmission",
    "drivetrain",
)


def _claim_payload(item: dict[str, object], *, requirement: bool) -> dict[str, object]:
    excluded = {"source_pages", "use_key"} if requirement else {"source_pages"}
    return {key: value for key, value in item.items() if key not in excluded}


def _raw_sha(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _case_key(dataset_key: str) -> str:
    return dataset_key.replace("reference-", "").replace("-repairs-v1", "").replace("-", ".")


class ReferenceFleetRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        self.fleet_index = json.loads(FLEET_INDEX_PATH.read_text(encoding="utf-8"))
        self.assertEqual(self.fleet_index["schema_version"], 1)
        datasets = self.fleet_index["datasets"]
        self.assertGreaterEqual(len(datasets), 1)
        self.assertEqual(len({item["path"] for item in datasets}), len(datasets))

    async def _run_reference_case(self, case: dict[str, object]) -> None:
        case_path = str(case["path"])
        case_root = REFERENCE_ROOT / case_path
        manifest = json.loads((case_root / str(case["manifest"])).read_text(encoding="utf-8"))
        reference = json.loads((case_root / str(case["repair"])).read_text(encoding="utf-8"))

        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(reference["schema_version"], 1)
        self.assertEqual(manifest["dataset_key"], reference["dataset_key"])
        self.assertEqual(len(manifest["sources"]), 1)
        self.assertEqual(len(manifest["repairs"]), 1)
        repair_manifest = manifest["repairs"][0]
        self.assertEqual(repair_manifest["repair_key"], reference["repair_key"])
        self.assertEqual(repair_manifest["path"], str(case["repair"]))
        self.assertEqual(repair_manifest["requirement_count"], len(reference["requirements"]))
        self.assertEqual(repair_manifest["action_count"], len(reference["actions"]))
        self.assertEqual(repair_manifest["capability_policy_key"], reference["capability_policy_key"])
        self.assertGreater(len(reference["requirements"]), 0)
        self.assertGreater(len(reference["actions"]), 0)

        source_definition = manifest["sources"][0]
        self.assertEqual(repair_manifest["source_key"], source_definition["source_key"])
        self.assertEqual(source_definition["source_class"], "oem_service")
        self.assertEqual(source_definition["license_status"], "approved")
        self.assertFalse(source_definition["automation_allowed"])

        db = session_factory()
        try:
            suffix = uuid4().hex[:12]
            now = datetime.now(UTC)
            case_key = _case_key(str(manifest["dataset_key"]))

            configuration, resolution = await resolve_configuration(
                db,
                VehicleConfigurationInput.model_validate(manifest["vehicle"]),
            )
            self.assertEqual(resolution, "created")
            self.assertEqual(configuration.verification_status, "unverified")
            original_identity = (
                configuration.year,
                configuration.market,
                configuration.make,
                configuration.model,
            )
            for field in OPTIONAL_IDENTITY_FIELDS:
                if manifest["vehicle"].get(field) is None:
                    self.assertIsNone(getattr(configuration, field))
            vehicle_configuration_id = configuration.id

            source = CatalogSource(
                id=uuid4(),
                source_key=f"phase8-{suffix}",
                display_name=str(source_definition["document"]),
                source_class=str(source_definition["source_class"]),
                license_status=str(source_definition["license_status"]),
                automation_allowed=False,
            )
            db.add(source)
            await db.flush()

            identity_payload = dict(manifest["vehicle"])
            identity_provenance: dict[str, object] = {
                "fixture": "reference-fleet-runtime",
                "dataset_key": manifest["dataset_key"],
            }
            if source_definition.get("document_part_number") is not None:
                identity_provenance["document_part_number"] = source_definition[
                    "document_part_number"
                ]
            identity_evidence = CatalogVerifiedEvidence(
                id=uuid4(),
                staging_record_id=uuid4(),
                candidate_type="mechanical_claim_candidate",
                verified_payload={"mechanical_claim": identity_payload},
                vehicle_identity={"vehicle_configuration_id": str(configuration.id)},
                source_name=source.source_key,
                source_type="oem_service",
                source_record_id=f"{manifest['dataset_key']}:{suffix}:vehicle-identity",
                source_url=str(source_definition["url"]),
                raw_sha256=_raw_sha(identity_payload),
                fetched_at=now,
                provenance=identity_provenance,
                extraction_method="reference_fixture",
                promoted_by="phase8-reference-reviewer",
            )
            identity_claim = MechanicalClaim(
                id=uuid4(),
                source_id=source.id,
                verified_evidence_id=identity_evidence.id,
                vehicle_configuration_id=configuration.id,
                claim_domain="vehicle_identity",
                claim_risk="normal",
                normalized_key=f"phase8.{case_key}.{suffix}.vehicle_identity",
                claim_payload=identity_payload,
                explicit_claim=True,
                exact_applicability=True,
                promotion_state="verified",
                reviewed_at=now,
                reviewed_by="phase8-reference-curator",
            )
            db.add_all([identity_evidence, identity_claim])
            await db.flush()

            await db.execute(text("SET LOCAL ROLE partgraph_materializer"))
            identity_publication = await materialize_verified_mechanical_claim_service(
                db,
                claim_id=identity_claim.id,
                actor="phase8-reference-curator",
                idempotency_key=f"phase8.{case_key}.identity.{suffix}",
            )
            self.assertEqual(identity_publication.record_id, configuration.id)
            self.assertEqual(identity_publication.canonical_domain, "vehicle_identity")
            await db.execute(text("RESET ROLE"))
            await db.refresh(configuration)
            self.assertEqual(configuration.verification_status, "verified")

            current = await db.scalar(
                select(RepairDefinition).where(
                    RepairDefinition.vehicle_configuration_id == configuration.id,
                    RepairDefinition.repair_key == reference["repair_key"],
                    RepairDefinition.status == "verified",
                )
            )
            self.assertIsNone(current)

            requirement_claim_ids: dict[str, UUID] = {}
            action_claim_ids: dict[str, UUID] = {}
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
                        vehicle_identity={"vehicle_configuration_id": str(configuration.id)},
                        source_name=source.source_key,
                        source_type="oem_service",
                        source_record_id=(
                            f"{manifest['dataset_key']}:{suffix}:{claim_domain}:{item_key}"
                        ),
                        source_url=str(source_definition["url"]),
                        raw_sha256=_raw_sha(payload),
                        fetched_at=now,
                        provenance={
                            "fixture": "reference-fleet-runtime",
                            "dataset_key": manifest["dataset_key"],
                            "source_pages": item.get("source_pages", []),
                        },
                        extraction_method="reference_fixture",
                        promoted_by="phase8-reference-reviewer",
                    )
                    claim = MechanicalClaim(
                        id=uuid4(),
                        source_id=source.id,
                        verified_evidence_id=evidence.id,
                        vehicle_configuration_id=configuration.id,
                        claim_domain=claim_domain,
                        claim_risk="normal",
                        normalized_key=(
                            f"phase8.{case_key}.{suffix}.{claim_domain}.{item_key}"
                        ),
                        repair_key=str(reference["repair_key"]),
                        claim_payload=payload,
                        explicit_claim=True,
                        exact_applicability=True,
                        promotion_state="verified",
                        reviewed_at=now,
                        reviewed_by="phase8-reference-curator",
                    )
                    db.add_all([evidence, claim])
                    target[item_key] = claim.id
            await db.flush()

            repair_request = RepairDefinitionMaterializationCreate(
                vehicle_configuration_id=configuration.id,
                repair_key=reference["repair_key"],
                title=reference["title"],
                capability_policy_key=reference["capability_policy_key"],
                operations=reference["operations"],
                requirements=[
                    {
                        **{key: value for key, value in item.items() if key != "source_pages"},
                        "supporting_claim_ids": [
                            requirement_claim_ids[str(item["use_key"])]
                        ],
                    }
                    for item in reference["requirements"]
                ],
                actions=[
                    {
                        **{key: value for key, value in item.items() if key != "source_pages"},
                        "supporting_claim_ids": [action_claim_ids[str(item["action_key"])]],
                    }
                    for item in reference["actions"]
                ],
            )

            await db.execute(text("SET LOCAL ROLE partgraph_materializer"))
            repair_publication = await materialize_repair_definition_service(
                db,
                request=repair_request,
                actor="phase8-reference-curator",
                idempotency_key=f"phase8.{case_key}.repair.{suffix}",
            )
            repair_definition_id = repair_publication.repair_definition_id
            await db.execute(text("RESET ROLE"))

            user = User(
                id=uuid4(),
                email=f"phase8-{suffix}@example.invalid",
                username=f"phase8_{suffix}",
                password_hash="phase8-reference-fixture",
                role="owner",
                is_active=True,
            )
            user_vehicle = UserVehicle(
                id=uuid4(),
                user_id=user.id,
                canonical_configuration_id=configuration.id,
                nickname=f"Phase 8 {configuration.make} {configuration.model}",
                identity_source="manual",
                identity_resolution="matched",
                identity_snapshot=dict(manifest["vehicle"]),
            )
            db.add_all([user, user_vehicle])
            await db.flush()

            await db.execute(text("SET LOCAL ROLE partgraph_app"))
            await set_user_context(db, user.id)
            device_id = uuid4()

            bundle = await create_repair_session(
                db,
                user_id=user.id,
                user_vehicle_id=user_vehicle.id,
                title=str(reference["title"]),
                device_id=device_id,
                idempotency_key=f"phase8_{suffix}_session",
            )
            session_id = bundle.repair_session.id

            binding = await bind_repair_definition(
                session_id,
                RepairDefinitionBind(repair_key=str(reference["repair_key"])),
                user,
                db,
                device_header=str(device_id),
            )
            self.assertEqual(binding.binding_state, "bound")
            self.assertEqual(binding.repair_definition_id, repair_definition_id)
            self.assertEqual(binding.vehicle_configuration_id, vehicle_configuration_id)

            readiness = await _readiness_view(
                db,
                user_id=user.id,
                repair_session=bundle.repair_session,
            )
            required_count = sum(
                item["necessity"] == "required" for item in reference["requirements"]
            )
            self.assertEqual(readiness.summary.total, len(reference["requirements"]))
            self.assertEqual(readiness.summary.missing, len(reference["requirements"]))
            self.assertEqual(readiness.summary.blocked, required_count)

            ordered_actions = sorted(reference["actions"], key=lambda item: item["position"])
            first_action = ordered_actions[0]
            requirements_by_use = {
                item["use_key"]: item for item in reference["requirements"]
            }
            expected_first_blockers = {
                requirements_by_use[use_key]["requirement_key"]
                for use_key in first_action.get("requirement_use_keys", [])
                if requirements_by_use[use_key]["necessity"] == "required"
            }
            blocked_guidance = await _guidance_view(
                db,
                user_id=user.id,
                session_id=session_id,
                include_plan=False,
            )
            if expected_first_blockers:
                self.assertEqual(blocked_guidance.status, "inventory_blocked")
                self.assertIsNotNone(blocked_guidance.current_action)
                assert blocked_guidance.current_action is not None
                self.assertEqual(
                    blocked_guidance.current_action.action_key,
                    first_action["action_key"],
                )
                self.assertEqual(
                    {
                        item.requirement_key
                        for item in blocked_guidance.current_action.inventory_blockers
                    },
                    expected_first_blockers,
                )

            for index, item in enumerate(readiness.requirements, start=1):
                readiness = await update_repair_readiness(
                    session_id,
                    item.requirement_definition_id,
                    RepairReadinessUpdate(readiness_state="have"),
                    user,
                    db,
                    device_header=str(device_id),
                    idempotency_header=f"phase8_{suffix}_ready_{index:02d}",
                )

            self.assertEqual(readiness.summary.ready, len(reference["requirements"]))
            self.assertEqual(readiness.summary.missing, 0)
            self.assertEqual(readiness.summary.blocked, 0)

            completed_keys: list[str] = []
            for index, expected_action in enumerate(ordered_actions, start=1):
                guidance = await _guidance_view(
                    db,
                    user_id=user.id,
                    session_id=session_id,
                    include_plan=False,
                )
                self.assertEqual(guidance.status, "action_available")
                self.assertIsNotNone(guidance.current_action)
                assert guidance.current_action is not None
                self.assertEqual(guidance.current_action.action_key, expected_action["action_key"])
                completed_keys.append(guidance.current_action.action_key)
                await update_action_progress(
                    session_id,
                    guidance.current_action.action_id,
                    GuidanceActionUpdate(progress_state="completed"),
                    user,
                    db,
                    device_header=str(device_id),
                    idempotency_header=f"phase8_{suffix}_action_{index:02d}",
                )

            self.assertEqual(
                completed_keys,
                [item["action_key"] for item in ordered_actions],
            )

            final_guidance = await _guidance_view(
                db,
                user_id=user.id,
                session_id=session_id,
                include_plan=False,
            )
            self.assertEqual(final_guidance.status, "procedure_complete")
            self.assertTrue(final_guidance.procedure_complete)
            self.assertEqual(final_guidance.summary.completed, len(ordered_actions))
            self.assertEqual(final_guidance.summary.pending, 0)

            completion = await _completion_view(
                db,
                user_id=user.id,
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
                db,
                user_id=user.id,
                session_id=session_id,
                after_sequence=0,
                limit=100,
            )
            self.assertEqual(
                sum(item.event_type == "readiness_state_changed" for item in history.items),
                len(reference["requirements"]),
            )
            self.assertEqual(
                sum(
                    item.event_type == "procedure_action_state_changed"
                    for item in history.items
                ),
                len(ordered_actions),
            )
            self.assertEqual(history.items[-1].payload["action_key"], ordered_actions[-1]["action_key"])
            self.assertEqual(history.items[-1].payload["progress_state"], "completed")

            stored_configuration = await db.get(VehicleConfiguration, vehicle_configuration_id)
            self.assertIsNotNone(stored_configuration)
            assert stored_configuration is not None
            self.assertEqual(stored_configuration.verification_status, "verified")
            self.assertEqual(
                (
                    stored_configuration.year,
                    stored_configuration.market,
                    stored_configuration.make,
                    stored_configuration.model,
                ),
                original_identity,
            )
            for field in OPTIONAL_IDENTITY_FIELDS:
                if manifest["vehicle"].get(field) is None:
                    self.assertIsNone(getattr(stored_configuration, field))
        finally:
            await db.rollback()
            await db.close()

    async def test_phase8_reference_fleet_uses_one_generic_runtime_path(self) -> None:
        for case in self.fleet_index["datasets"]:
            with self.subTest(dataset=case["path"]):
                await self._run_reference_case(case)


if __name__ == "__main__":
    unittest.main()
