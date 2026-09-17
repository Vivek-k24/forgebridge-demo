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
from partgraph.repair_experience.service import (
    create_repair_session,
    event_history,
)

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
REFERENCE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "reference"
    / "2015_toyota_camry_repairs_v1"
)
MANIFEST_PATH = REFERENCE_ROOT / "manifest.json"
REPAIR_PATH = REFERENCE_ROOT / "license_plate_light_bulb_replacement.json"


def _claim_payload(item: dict[str, object], *, requirement: bool) -> dict[str, object]:
    excluded = {"source_pages", "use_key"} if requirement else {"source_pages"}
    return {key: value for key, value in item.items() if key not in excluded}


def _raw_sha(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class ReferenceFleetCamryRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.reference = json.loads(REPAIR_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            self.manifest["vehicle"],
            {"market": "US", "year": 2015, "make": "Toyota", "model": "CAMRY"},
        )
        self.assertEqual(self.reference["repair_key"], "license-plate-light-bulb-replacement")
        self.assertEqual(len(self.reference["requirements"]), 3)
        self.assertEqual(len(self.reference["actions"]), 4)

        self.db = session_factory()
        self.addAsyncCleanup(self.db.close)
        suffix = uuid4().hex[:12]
        now = datetime.now(UTC)

        configuration, resolution = await resolve_configuration(
            self.db,
            VehicleConfigurationInput.model_validate(self.manifest["vehicle"]),
        )
        self.assertEqual(resolution, "created")
        self.assertEqual(configuration.verification_status, "unverified")
        self.assertEqual(
            (
                configuration.year,
                configuration.market,
                configuration.make,
                configuration.model,
                configuration.trim,
                configuration.engine,
                configuration.transmission,
                configuration.drivetrain,
            ),
            (2015, "US", "Toyota", "CAMRY", None, None, None, None),
        )
        self.vehicle_configuration_id = configuration.id

        source_definition = self.manifest["sources"][0]
        self.source = CatalogSource(
            id=uuid4(),
            source_key=f"phase8-camry-{suffix}",
            display_name="2015 Toyota Camry owner manual reference fixture",
            source_class=source_definition["source_class"],
            license_status=source_definition["license_status"],
            automation_allowed=False,
        )
        self.db.add(self.source)
        await self.db.flush()

        identity_payload = dict(self.manifest["vehicle"])
        identity_evidence = CatalogVerifiedEvidence(
            id=uuid4(),
            staging_record_id=uuid4(),
            candidate_type="mechanical_claim_candidate",
            verified_payload={"mechanical_claim": identity_payload},
            vehicle_identity={"vehicle_configuration_id": str(configuration.id)},
            source_name=self.source.source_key,
            source_type="oem_service",
            source_record_id=f"phase8-camry:{suffix}:vehicle-identity",
            source_url=source_definition["url"],
            raw_sha256=_raw_sha(identity_payload),
            fetched_at=now,
            provenance={
                "fixture": "reference-fleet-runtime",
                "dataset_key": self.manifest["dataset_key"],
                "document_part_number": source_definition["document_part_number"],
            },
            extraction_method="reference_fixture",
            promoted_by="phase8-reference-reviewer",
        )
        identity_claim = MechanicalClaim(
            id=uuid4(),
            source_id=self.source.id,
            verified_evidence_id=identity_evidence.id,
            vehicle_configuration_id=configuration.id,
            claim_domain="vehicle_identity",
            claim_risk="normal",
            normalized_key=f"phase8.camry.{suffix}.vehicle_identity",
            claim_payload=identity_payload,
            explicit_claim=True,
            exact_applicability=True,
            promotion_state="verified",
            reviewed_at=now,
            reviewed_by="phase8-reference-curator",
        )
        self.db.add_all([identity_evidence, identity_claim])
        await self.db.flush()

        await self.db.execute(text("SET LOCAL ROLE partgraph_materializer"))
        identity_publication = await materialize_verified_mechanical_claim_service(
            self.db,
            claim_id=identity_claim.id,
            actor="phase8-reference-curator",
            idempotency_key=f"phase8.camry.identity.{suffix}",
        )
        self.assertEqual(identity_publication.record_id, configuration.id)
        self.assertEqual(identity_publication.canonical_domain, "vehicle_identity")
        await self.db.execute(text("RESET ROLE"))
        await self.db.refresh(configuration)
        self.assertEqual(configuration.verification_status, "verified")

        current = await self.db.scalar(
            select(RepairDefinition).where(
                RepairDefinition.vehicle_configuration_id == configuration.id,
                RepairDefinition.repair_key == self.reference["repair_key"],
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
                    vehicle_identity={"vehicle_configuration_id": str(configuration.id)},
                    source_name=self.source.source_key,
                    source_type="oem_service",
                    source_record_id=f"phase8-camry:{suffix}:{claim_domain}:{item_key}",
                    source_url=source_definition["url"],
                    raw_sha256=_raw_sha(payload),
                    fetched_at=now,
                    provenance={
                        "fixture": "reference-fleet-runtime",
                        "dataset_key": self.manifest["dataset_key"],
                        "source_pages": item.get("source_pages", []),
                    },
                    extraction_method="reference_fixture",
                    promoted_by="phase8-reference-reviewer",
                )
                claim = MechanicalClaim(
                    id=uuid4(),
                    source_id=self.source.id,
                    verified_evidence_id=evidence.id,
                    vehicle_configuration_id=configuration.id,
                    claim_domain=claim_domain,
                    claim_risk="normal",
                    normalized_key=f"phase8.camry.{suffix}.{claim_domain}.{item_key}",
                    repair_key=self.reference["repair_key"],
                    claim_payload=payload,
                    explicit_claim=True,
                    exact_applicability=True,
                    promotion_state="verified",
                    reviewed_at=now,
                    reviewed_by="phase8-reference-curator",
                )
                self.db.add_all([evidence, claim])
                target[item_key] = claim.id
        await self.db.flush()

        repair_request = RepairDefinitionMaterializationCreate(
            vehicle_configuration_id=configuration.id,
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
        repair_publication = await materialize_repair_definition_service(
            self.db,
            request=repair_request,
            actor="phase8-reference-curator",
            idempotency_key=f"phase8.camry.repair.{suffix}",
        )
        self.repair_definition_id = repair_publication.repair_definition_id
        await self.db.execute(text("RESET ROLE"))

        self.user = User(
            id=uuid4(),
            email=f"phase8-camry-{suffix}@example.invalid",
            username=f"phase8_camry_{suffix}",
            password_hash="phase8-reference-fixture",
            role="owner",
            is_active=True,
        )
        self.user_vehicle = UserVehicle(
            id=uuid4(),
            user_id=self.user.id,
            canonical_configuration_id=configuration.id,
            nickname="Phase 8 Camry",
            identity_source="manual",
            identity_resolution="matched",
            identity_snapshot=dict(self.manifest["vehicle"]),
        )
        self.db.add_all([self.user, self.user_vehicle])
        await self.db.flush()

        await self.db.execute(text("SET LOCAL ROLE partgraph_app"))
        await set_user_context(self.db, self.user.id)
        self.device_id = uuid4()

    async def test_camry_runs_through_generic_repair_runtime(self) -> None:
        bundle = await create_repair_session(
            self.db,
            user_id=self.user.id,
            user_vehicle_id=self.user_vehicle.id,
            title=self.reference["title"],
            device_id=self.device_id,
            idempotency_key="phase8_camry_session",
        )
        session_id = bundle.repair_session.id

        binding = await bind_repair_definition(
            session_id,
            RepairDefinitionBind(repair_key=self.reference["repair_key"]),
            self.user,
            self.db,
            device_header=str(self.device_id),
        )
        self.assertEqual(binding.binding_state, "bound")
        self.assertEqual(binding.repair_definition_id, self.repair_definition_id)
        self.assertEqual(binding.vehicle_configuration_id, self.vehicle_configuration_id)

        readiness = await _readiness_view(
            self.db,
            user_id=self.user.id,
            repair_session=bundle.repair_session,
        )
        self.assertEqual(readiness.summary.total, 3)
        self.assertEqual(readiness.summary.missing, 3)
        self.assertEqual(readiness.summary.blocked, 3)

        blocked_guidance = await _guidance_view(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
            include_plan=False,
        )
        self.assertEqual(blocked_guidance.status, "inventory_blocked")
        self.assertIsNotNone(blocked_guidance.current_action)
        assert blocked_guidance.current_action is not None
        self.assertEqual(blocked_guidance.current_action.action_key, "prepare-replacement-bulb")
        self.assertEqual(
            {item.requirement_key for item in blocked_guidance.current_action.inventory_blockers},
            {"part.license_plate_light_bulb.w5w_5w_clear"},
        )

        for index, item in enumerate(readiness.requirements, start=1):
            readiness = await update_repair_readiness(
                session_id,
                item.requirement_definition_id,
                RepairReadinessUpdate(readiness_state="have"),
                self.user,
                self.db,
                device_header=str(self.device_id),
                idempotency_header=f"phase8_camry_ready_{index:02d}",
            )

        self.assertEqual(readiness.summary.ready, 3)
        self.assertEqual(readiness.summary.missing, 0)
        self.assertEqual(readiness.summary.blocked, 0)

        completed_keys: list[str] = []
        for index in range(1, 5):
            guidance = await _guidance_view(
                self.db,
                user_id=self.user.id,
                session_id=session_id,
                include_plan=False,
            )
            self.assertEqual(guidance.status, "action_available")
            self.assertIsNotNone(guidance.current_action)
            assert guidance.current_action is not None
            completed_keys.append(guidance.current_action.action_key)
            await update_action_progress(
                session_id,
                guidance.current_action.action_id,
                GuidanceActionUpdate(progress_state="completed"),
                self.user,
                self.db,
                device_header=str(self.device_id),
                idempotency_header=f"phase8_camry_action_{index:02d}",
            )

        self.assertEqual(
            completed_keys,
            [
                "prepare-replacement-bulb",
                "remove-license-plate-light-cover",
                "remove-lens-and-old-bulb",
                "install-bulb-and-restore-cover",
            ],
        )

        final_guidance = await _guidance_view(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
            include_plan=False,
        )
        self.assertEqual(final_guidance.status, "procedure_complete")
        self.assertTrue(final_guidance.procedure_complete)
        self.assertEqual(final_guidance.summary.completed, 4)
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
        self.assertEqual(sum(item.event_type == "readiness_state_changed" for item in history.items), 3)
        self.assertEqual(
            sum(item.event_type == "procedure_action_state_changed" for item in history.items),
            4,
        )
        self.assertEqual(history.items[-1].payload["action_key"], "install-bulb-and-restore-cover")
        self.assertEqual(history.items[-1].payload["progress_state"], "completed")

        configuration = await self.db.get(VehicleConfiguration, self.vehicle_configuration_id)
        self.assertIsNotNone(configuration)
        assert configuration is not None
        self.assertEqual(configuration.verification_status, "verified")
        self.assertEqual((configuration.year, configuration.make, configuration.model), (2015, "Toyota", "CAMRY"))
        self.assertIsNone(configuration.trim)


if __name__ == "__main__":
    unittest.main()
