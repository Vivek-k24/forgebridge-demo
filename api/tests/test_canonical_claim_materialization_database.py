import os
import unittest
from datetime import UTC, datetime
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb
from sqlalchemy import text

from partgraph.database import session_factory
from partgraph.errors import ErrorCode, PartGraphError
from partgraph.knowledge.canonical_claim_materialization import (
    materialize_verified_mechanical_claim_service,
)

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
MATERIALIZER_ROLE = "partgraph_materializer"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class CanonicalClaimMaterializationDatabaseTests(unittest.IsolatedAsyncioTestCase):
    vehicle_id: UUID
    incomplete_vehicle_id: UUID
    role_id: UUID
    vehicle_claim_id: UUID
    incomplete_vehicle_claim_id: UUID
    fitment_claim_id: UUID
    safety_claim_id: UUID

    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        suffix = uuid4().hex[:12]
        now = datetime.now(UTC)
        self.vehicle_id = uuid4()
        self.incomplete_vehicle_id = uuid4()
        vehicle_source_id = uuid4()
        fitment_source_id = uuid4()
        safety_source_id = uuid4()
        component_id = uuid4()
        part_id = uuid4()
        self.role_id = uuid4()
        self.vehicle_claim_id = uuid4()
        self.incomplete_vehicle_claim_id = uuid4()
        self.fitment_claim_id = uuid4()
        self.safety_claim_id = uuid4()

        complete_identity = {
            "year": 2024,
            "market": "US",
            "make": "Fixture",
            "model": "Canonical",
            "generation": "G1",
            "trim": "Exact",
            "body_style": "Sedan",
            "engine": "2.0L I4",
            "transmission": "CVT",
            "drivetrain": "FWD",
        }
        incomplete_identity = {
            "year": 2025,
            "market": "US",
            "make": "Fixture",
            "model": "Incomplete",
        }
        fitment_payload = {
            "component_part_role_id": str(self.role_id),
            "applicability_state": "applicable",
            "qualifier_key": "",
            "qualifiers": {},
        }
        safety_payload = {
            "campaign_number": "TEST-001",
            "component": "Fixture component",
            "issue": "Fixture safety issue",
            "remedy": "Fixture remedy",
        }

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.vehicle_configurations
                        (id, identity_hash, base_identity_hash, canonicalization_version,
                         year, market, make, model, generation, trim, body_style,
                         engine, transmission, drivetrain, identity_source,
                         verification_status)
                    VALUES
                        (%s, %s, %s, 2, 2024, 'US', 'Fixture', 'Canonical', 'G1',
                         'Exact', 'Sedan', '2.0L I4', 'CVT', 'FWD', 'fixture', 'unverified'),
                        (%s, %s, %s, 2, 2025, 'US', 'Fixture', 'Incomplete', 'G2',
                         'Exact', 'SUV', '2.5L I4', 'Automatic', 'AWD', 'fixture', 'unverified')
                    """,
                    (
                        self.vehicle_id,
                        uuid4().hex * 2,
                        uuid4().hex * 2,
                        self.incomplete_vehicle_id,
                        uuid4().hex * 2,
                        uuid4().hex * 2,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO public.catalog_sources
                        (id, source_key, display_name, source_class,
                         license_status, automation_allowed)
                    VALUES
                        (%s, %s, 'Vehicle identity fixture', 'oem_service', 'approved', false),
                        (%s, %s, 'Part fitment fixture', 'oem_parts', 'approved', false),
                        (%s, %s, 'Safety campaign fixture', 'government', 'approved', true)
                    """,
                    (
                        vehicle_source_id,
                        f"vehicle-materialization-{suffix}",
                        fitment_source_id,
                        f"fitment-materialization-{suffix}",
                        safety_source_id,
                        f"safety-materialization-{suffix}",
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO public.component_definitions (id, component_key, display_name)
                    VALUES (%s, %s, 'Fixture component')
                    """,
                    (component_id, f"fixture.component.{suffix}"),
                )
                cursor.execute(
                    """
                    INSERT INTO public.part_identities
                        (id, manufacturer, part_number, revision, display_name)
                    VALUES (%s, 'Fixture OEM', %s, '', 'Fixture part')
                    """,
                    (part_id, f"PG-{suffix}"),
                )
                cursor.execute(
                    """
                    INSERT INTO public.component_part_roles
                        (id, component_id, part_id, position_key)
                    VALUES (%s, %s, %s, 'front')
                    """,
                    (self.role_id, component_id, part_id),
                )

                fixtures = (
                    (
                        self.vehicle_claim_id,
                        vehicle_source_id,
                        f"vehicle-materialization-{suffix}",
                        "oem_service",
                        self.vehicle_id,
                        "vehicle_identity",
                        "normal",
                        f"vehicle:fixture:{suffix}",
                        complete_identity,
                    ),
                    (
                        self.incomplete_vehicle_claim_id,
                        vehicle_source_id,
                        f"vehicle-materialization-{suffix}",
                        "oem_service",
                        self.incomplete_vehicle_id,
                        "vehicle_identity",
                        "normal",
                        f"vehicle:incomplete:{suffix}",
                        incomplete_identity,
                    ),
                    (
                        self.fitment_claim_id,
                        fitment_source_id,
                        f"fitment-materialization-{suffix}",
                        "oem_parts",
                        self.vehicle_id,
                        "part_fitment",
                        "normal",
                        f"fitment:fixture:{suffix}",
                        fitment_payload,
                    ),
                    (
                        self.safety_claim_id,
                        safety_source_id,
                        f"safety-materialization-{suffix}",
                        "government",
                        self.vehicle_id,
                        "safety_campaign",
                        "normal",
                        f"safety:fixture:{suffix}",
                        safety_payload,
                    ),
                )
                for (
                    claim_id,
                    source_id,
                    source_key,
                    source_type,
                    vehicle_id,
                    claim_domain,
                    claim_risk,
                    normalized_key,
                    payload,
                ) in fixtures:
                    evidence_id = uuid4()
                    cursor.execute(
                        """
                        INSERT INTO public.catalog_verified_evidence
                            (id, staging_record_id, candidate_type, verified_payload,
                             vehicle_identity, source_name, source_type, source_record_id,
                             source_url, raw_sha256, fetched_at, provenance,
                             extraction_method, promoted_by)
                        VALUES (%s, %s, 'mechanical_claim_candidate', %s, %s,
                                %s, %s, %s, %s, %s, %s, %s,
                                'fixture', 'fixture-reviewer')
                        """,
                        (
                            evidence_id,
                            uuid4(),
                            Jsonb({"mechanical_claim": payload}),
                            Jsonb({"vehicle_configuration_id": str(vehicle_id)}),
                            source_key,
                            source_type,
                            f"record-{claim_id}",
                            f"https://example.invalid/canonical/{claim_id}",
                            uuid4().hex * 2,
                            now,
                            Jsonb({"fixture": True}),
                        ),
                    )
                    cursor.execute(
                        """
                        INSERT INTO public.mechanical_claims
                            (id, source_id, verified_evidence_id, vehicle_configuration_id,
                             claim_domain, claim_risk, normalized_key, claim_payload,
                             explicit_claim, exact_applicability, promotion_state,
                             reviewed_at, reviewed_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                                true, true, 'verified', %s, 'fixture-curator')
                        """,
                        (
                            claim_id,
                            source_id,
                            evidence_id,
                            vehicle_id,
                            claim_domain,
                            claim_risk,
                            normalized_key,
                            Jsonb(payload),
                            now,
                        ),
                    )

    async def _publish(self, claim_id: UUID, key: str):
        async with session_factory() as session:
            async with session.begin():
                await session.execute(text(f"SET LOCAL ROLE {MATERIALIZER_ROLE}"))
                return await materialize_verified_mechanical_claim_service(
                    session,
                    claim_id=claim_id,
                    actor="fixture-curator:curator",
                    idempotency_key=key,
                )

    async def test_vehicle_identity_materialization_versions_existing_configuration(self) -> None:
        key = f"identity:test:{uuid4().hex}"
        first = await self._publish(self.vehicle_claim_id, key)
        self.assertEqual(first.claim_domain, "vehicle_identity")
        self.assertEqual(first.canonical_domain, "vehicle_identity")
        self.assertEqual(first.record_type, "vehicle_configuration")
        self.assertEqual(first.record_id, self.vehicle_id)
        self.assertEqual(first.version, 1)
        self.assertFalse(first.idempotent)

        repeated = await self._publish(self.vehicle_claim_id, key)
        self.assertTrue(repeated.idempotent)
        self.assertEqual(repeated.canonical_record_version_id, first.canonical_record_version_id)

        repeated_with_new_key = await self._publish(
            self.vehicle_claim_id,
            f"identity:test:{uuid4().hex}",
        )
        self.assertTrue(repeated_with_new_key.idempotent)
        self.assertEqual(
            repeated_with_new_key.canonical_record_version_id,
            first.canonical_record_version_id,
        )

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT verification_status FROM public.vehicle_configurations WHERE id = %s",
                    (self.vehicle_id,),
                )
                self.assertEqual(cursor.fetchone()[0], "verified")
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM public.canonical_record_evidence
                    WHERE mechanical_claim_id = %s
                    """,
                    (self.vehicle_claim_id,),
                )
                self.assertEqual(cursor.fetchone()[0], 1)

        with self.assertRaises(PartGraphError) as context:
            await self._publish(self.fitment_claim_id, key)
        self.assertEqual(
            context.exception.code,
            ErrorCode.KNOWLEDGE_PUBLICATION_IDEMPOTENCY_CONFLICT,
        )

    async def test_unverified_vehicle_requires_full_identity_coverage(self) -> None:
        with self.assertRaises(PartGraphError) as context:
            await self._publish(
                self.incomplete_vehicle_claim_id,
                f"identity:test:{uuid4().hex}",
            )
        self.assertEqual(
            context.exception.code,
            ErrorCode.KNOWLEDGE_MATERIALIZATION_INVALID,
        )
        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT verification_status FROM public.vehicle_configurations WHERE id = %s",
                    (self.incomplete_vehicle_id,),
                )
                self.assertEqual(cursor.fetchone()[0], "unverified")

    async def test_part_fitment_materialization_is_insert_only_and_idempotent(self) -> None:
        first = await self._publish(
            self.fitment_claim_id,
            f"fitment:test:{uuid4().hex}",
        )
        self.assertEqual(first.claim_domain, "part_fitment")
        self.assertEqual(first.canonical_domain, "fitment")
        self.assertEqual(first.record_type, "part_fitment")
        self.assertEqual(first.version, 1)

        repeated = await self._publish(
            self.fitment_claim_id,
            f"fitment:test:{uuid4().hex}",
        )
        self.assertTrue(repeated.idempotent)
        self.assertEqual(repeated.record_id, first.record_id)

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT vehicle_configuration_id, component_part_role_id,
                           applicability_state, qualifier_key, qualifiers
                    FROM public.part_fitments
                    WHERE id = %s
                    """,
                    (first.record_id,),
                )
                row = cursor.fetchone()
                self.assertEqual(row[0], self.vehicle_id)
                self.assertEqual(row[1], self.role_id)
                self.assertEqual(row[2], "applicable")
                self.assertEqual(row[3], "")
                self.assertEqual(row[4], {})

    async def test_safety_campaign_has_no_canonical_materializer(self) -> None:
        with self.assertRaises(PartGraphError) as context:
            await self._publish(
                self.safety_claim_id,
                f"safety:test:{uuid4().hex}",
            )
        self.assertEqual(
            context.exception.code,
            ErrorCode.KNOWLEDGE_MATERIALIZATION_INVALID,
        )
        self.assertIn("no canonical materializer", context.exception.message)

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM public.canonical_record_evidence
                    WHERE mechanical_claim_id = %s
                    """,
                    (self.safety_claim_id,),
                )
                self.assertEqual(cursor.fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
