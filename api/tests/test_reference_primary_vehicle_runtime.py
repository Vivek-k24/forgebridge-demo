import hashlib
import json
import os
import unittest
from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID, uuid4

from PIL import Image
from reference_fixture_support import (
    primary_profile_file,
    primary_vehicle_id,
    primary_vehicle_snapshot,
)
from sqlalchemy import select, text

import partgraph.orm_registry  # noqa: F401
from partgraph.database import session_factory
from partgraph.identity.auth.models import User
from partgraph.identity.auth.service import set_user_context
from partgraph.identity.user_vehicle.models import UserVehicle
from partgraph.identity.vehicle.models import VehicleConfiguration
from partgraph.knowledge.models import CatalogSource, CatalogVerifiedEvidence, MechanicalClaim
from partgraph.knowledge.specifications import SpecificationDefinition, VehicleSpecificationValue
from partgraph.knowledge.vehicle_domain_materialization import (
    materialize_vehicle_domain_claim_service,
)
from partgraph.knowledge.vehicle_structure import VehicleStructureNode
from partgraph.repair_experience.memory_models import RepairPhotoEvidence
from partgraph.repair_experience.memory.schemas import ObservationCreate
from partgraph.repair_experience.memory.service import (
    create_observation,
    create_photo,
    delete_photo,
    list_observations,
    list_photos,
)
from partgraph.repair_experience.service import create_repair_session

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
REFERENCE_VEHICLE_ID = primary_vehicle_id()
REFERENCE_VEHICLE = primary_vehicle_snapshot()


def _raw_sha(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _structure_payload(item: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in item.items()
        if key not in {"source_key", "evidence_note"}
    }


def _specification_payload(item: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in item.items()
        if key not in {"source_key", "source_pages"}
    }


class ReferencePrimaryVehicleRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def _cleanup_db(self) -> None:
        if hasattr(self, "transaction") and self.transaction.is_active:
            await self.transaction.rollback()
        if hasattr(self, "db"):
            await self.db.close()

    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        _, self.coverage = primary_profile_file("canonical_coverage")
        self.assertEqual(
            self.coverage["vehicle_configuration_id"],
            str(REFERENCE_VEHICLE_ID),
        )
        self.assertEqual(self.coverage["review"]["status"], "approved_reference_derivation")

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

        suffix = uuid4().hex[:12]
        now = datetime.now(UTC)
        source_rows: dict[str, CatalogSource] = {}
        for source_key, source in self.coverage["sources"].items():
            row = CatalogSource(
                id=uuid4(),
                source_key=f"phase7-{source_key[:70]}-{suffix}",
                display_name=f"Phase 7 reviewed source: {source_key}",
                source_class=source["source_class"],
                license_status=source["license_status"],
                automation_allowed=bool(source["automation_allowed"]),
                notes="Reference Phase 7 runtime fixture; source facts remain data-driven.",
            )
            source_rows[source_key] = row
            self.db.add(row)

        self.user = User(
            id=uuid4(),
            email=f"phase7-reference-{suffix}@example.invalid",
            username=f"phase7_{suffix}",
            password_hash="phase7-reference-fixture",
            role="owner",
            is_active=True,
        )
        self.user_vehicle = UserVehicle(
            id=uuid4(),
            user_id=self.user.id,
            canonical_configuration_id=REFERENCE_VEHICLE_ID,
            nickname="Primary reference vehicle",
            identity_source="manual",
            identity_resolution="matched",
            identity_snapshot=dict(REFERENCE_VEHICLE),
        )
        self.db.add_all([self.user, self.user_vehicle])
        await self.db.flush()

        self.structure_claims: dict[str, UUID] = {}
        self.specification_claims: dict[str, UUID] = {}
        for claim_domain, items, payload_builder, key_field, target in (
            (
                "vehicle_structure",
                self.coverage["structure"],
                _structure_payload,
                "node_key",
                self.structure_claims,
            ),
            (
                "vehicle_specification",
                self.coverage["specifications"],
                _specification_payload,
                "specification_key",
                self.specification_claims,
            ),
        ):
            for item in items:
                source_key = str(item["source_key"])
                source = source_rows[source_key]
                payload = payload_builder(item)
                fact_key = str(item[key_field])
                evidence = CatalogVerifiedEvidence(
                    id=uuid4(),
                    staging_record_id=uuid4(),
                    candidate_type="mechanical_claim_candidate",
                    verified_payload={"mechanical_claim": payload},
                    vehicle_identity={
                        "vehicle_configuration_id": str(REFERENCE_VEHICLE_ID)
                    },
                    source_name=source_key,
                    source_type=source.source_class,
                    source_record_id=f"phase7:{claim_domain}:{fact_key}",
                    source_url=str(self.coverage["sources"][source_key]["url"]),
                    raw_sha256=_raw_sha(payload),
                    fetched_at=now,
                    provenance={
                        "fixture": "reference-primary-vehicle-runtime",
                        "review_status": self.coverage["review"]["status"],
                        "automation_allowed": source.automation_allowed,
                    },
                    extraction_method="reference_fixture",
                    promoted_by="phase7-reference-reviewer",
                )
                claim = MechanicalClaim(
                    id=uuid4(),
                    source_id=source.id,
                    verified_evidence_id=evidence.id,
                    vehicle_configuration_id=REFERENCE_VEHICLE_ID,
                    claim_domain=claim_domain,
                    claim_risk="normal",
                    normalized_key=f"phase7.{claim_domain}.{fact_key}",
                    claim_payload=payload,
                    explicit_claim=True,
                    exact_applicability=True,
                    promotion_state="verified",
                    reviewed_at=now,
                    reviewed_by="phase7-reference-curator",
                )
                self.db.add_all([evidence, claim])
                target[fact_key] = claim.id
        await self.db.flush()

        await self.db.execute(text("SET LOCAL ROLE partgraph_materializer"))
        for item in self.coverage["structure"]:
            fact_key = str(item["node_key"])
            await materialize_vehicle_domain_claim_service(
                self.db,
                claim_id=self.structure_claims[fact_key],
                actor="phase7-reference-curator",
                idempotency_key=f"phase7-structure-{fact_key}-{suffix}",
            )
        for item in self.coverage["specifications"]:
            fact_key = str(item["specification_key"])
            await materialize_vehicle_domain_claim_service(
                self.db,
                claim_id=self.specification_claims[fact_key],
                actor="phase7-reference-curator",
                idempotency_key=f"phase7-spec-{fact_key[:55]}-{suffix}",
            )

        await self.db.execute(text("RESET ROLE"))
        await self.db.execute(text("SET LOCAL ROLE partgraph_app"))
        await set_user_context(self.db, self.user.id)
        self.device_id = uuid4()

    async def test_reference_structure_and_specifications_are_canonical(self) -> None:
        nodes = list(
            await self.db.scalars(
                select(VehicleStructureNode).where(
                    VehicleStructureNode.vehicle_configuration_id == REFERENCE_VEHICLE_ID
                )
            )
        )
        by_key = {node.node_key: node for node in nodes}
        self.assertEqual(by_key["engine"].node_type, "system")
        self.assertEqual(by_key["engine-cooling"].parent_node_id, by_key["engine"].id)
        self.assertEqual(by_key["engine-water-pump"].node_type, "assembly")
        self.assertEqual(
            by_key["engine-water-pump"].parent_node_id,
            by_key["engine-cooling"].id,
        )

        values = list(
            await self.db.scalars(
                select(VehicleSpecificationValue).where(
                    VehicleSpecificationValue.vehicle_configuration_id == REFERENCE_VEHICLE_ID
                )
            )
        )
        self.assertEqual(len(values), 2)
        definitions = {
            row.id: row
            for row in await self.db.scalars(
                select(SpecificationDefinition).where(
                    SpecificationDefinition.id.in_(
                        {value.specification_definition_id for value in values}
                    )
                )
            )
        }
        by_key_value = {
            definitions[value.specification_definition_id].specification_key: value
            for value in values
        }
        expected_specs = {
            str(item["specification_key"]): item
            for item in self.coverage["specifications"]
        }
        capacity = by_key_value["engine-oil-change-capacity-with-filter"]
        expected_capacity = expected_specs["engine-oil-change-capacity-with-filter"]
        self.assertEqual(
            float(capacity.nominal_value),
            float(expected_capacity["nominal_value"]),
        )
        self.assertEqual(capacity.unit, expected_capacity["unit"])
        torque = by_key_value["engine-oil-drain-bolt-torque"]
        expected_torque = expected_specs["engine-oil-drain-bolt-torque"]
        self.assertEqual(
            float(torque.nominal_value),
            float(expected_torque["nominal_value"]),
        )
        self.assertEqual(torque.unit, expected_torque["unit"])

    async def test_owner_observation_and_photo_evidence_round_trip(self) -> None:
        bundle = await create_repair_session(
            self.db,
            user_id=self.user.id,
            user_vehicle_id=self.user_vehicle.id,
            title="Phase 7 observation and photo proof",
            device_id=self.device_id,
            idempotency_key="phase7_owner_memory_session",
        )
        session_id = bundle.repair_session.id
        observation = await create_observation(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
            device_id=self.device_id,
            idempotency_key="phase7_owner_observation",
            payload=ObservationCreate(
                category="current_step",
                text="Water-pump area is exposed and ready for a before-work photo.",
            ),
        )
        self.assertEqual(observation.source, "user")
        self.assertEqual(observation.review_state, "confirmed")

        image_buffer = BytesIO()
        Image.new("RGB", (2, 2), (80, 120, 160)).save(image_buffer, format="PNG")
        image_bytes = image_buffer.getvalue()
        photo = await create_photo(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
            device_id=self.device_id,
            idempotency_key="phase7_owner_photo",
            purpose="current_step",
            observation_id=observation.id,
            fastener_id=None,
            filename="water-pump-before.png",
            data=image_bytes,
            maximum_bytes=1024 * 1024,
        )
        self.assertEqual(photo.observation_id, observation.id)
        self.assertEqual(photo.media_type, "image/png")
        self.assertEqual(photo.sha256, hashlib.sha256(image_bytes).hexdigest())

        observations = await list_observations(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
        )
        photos = await list_photos(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
        )
        self.assertEqual([item.id for item in observations], [observation.id])
        self.assertEqual([item.id for item in photos], [photo.id])

        photo_row = await self.db.get(RepairPhotoEvidence, photo.id)
        self.assertIsNotNone(photo_row)
        assert photo_row is not None
        self.assertEqual(photo_row.storage_state, "pending_upload")
        self.assertEqual(bytes(photo_row.pending_content or b""), image_bytes)

        deleted = await delete_photo(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
            photo_id=photo.id,
            device_id=self.device_id,
            idempotency_key="phase7_owner_photo_delete",
        )
        self.assertEqual(deleted.id, photo.id)
        self.assertEqual(photo_row.storage_state, "delete_pending")
        self.assertIsNotNone(photo_row.deleted_at)
        self.assertIsNone(photo_row.pending_content)
        self.assertEqual(
            await list_photos(self.db, user_id=self.user.id, session_id=session_id),
            [],
        )


if __name__ == "__main__":
    unittest.main()
