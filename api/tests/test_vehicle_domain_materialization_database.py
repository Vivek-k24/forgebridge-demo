import os
import unittest
from datetime import UTC, datetime
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb
from sqlalchemy import text

from partgraph.database import session_factory
from partgraph.knowledge.vehicle_domain_materialization import (
    materialize_vehicle_domain_claim_service,
)

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
MATERIALIZER_ROLE = "partgraph_materializer"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class VehicleDomainMaterializationDatabaseTests(unittest.IsolatedAsyncioTestCase):
    vehicle_id: UUID
    engine_claim_id: UUID
    cooling_claim_id: UUID
    pump_claim_id: UUID
    capacity_claim_id: UUID

    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        suffix = uuid4().hex[:12]
        now = datetime.now(UTC)
        self.vehicle_id = uuid4()
        source_id = uuid4()
        self.engine_claim_id = uuid4()
        self.cooling_claim_id = uuid4()
        self.pump_claim_id = uuid4()
        self.capacity_claim_id = uuid4()
        source_key = f"vehicle-domain-materialization-{suffix}"

        structure_payloads = (
            (
                self.engine_claim_id,
                "structure:engine",
                {
                    "node_key": "engine",
                    "node_type": "system",
                    "display_name": "Engine",
                    "parent_node_key": None,
                    "placement": "front",
                    "position": 0,
                },
            ),
            (
                self.cooling_claim_id,
                "structure:engine-cooling",
                {
                    "node_key": "engine-cooling",
                    "node_type": "subsystem",
                    "display_name": "Engine cooling system",
                    "parent_node_key": "engine",
                    "placement": "front",
                    "position": 0,
                },
            ),
            (
                self.pump_claim_id,
                "structure:engine-water-pump",
                {
                    "node_key": "engine-water-pump",
                    "node_type": "assembly",
                    "display_name": "Engine water-pump assembly",
                    "parent_node_key": "engine-cooling",
                    "placement": "front",
                    "position": 0,
                },
            ),
        )
        capacity_payload = {
            "specification_key": "engine-oil-change-capacity-with-filter",
            "specification_type": "capacity",
            "value_kind": "scalar",
            "display_name": "Engine oil change capacity with filter",
            "quantity_kind": "volume",
            "description": "Fixture capacity",
            "application_key": "engine-oil-change",
            "nominal_value": "3.4",
            "unit": "US qt",
            "qualifier_key": "with-filter",
            "conditions": {"filter_replaced": True},
        }

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.vehicle_configurations
                        (id, identity_hash, base_identity_hash, canonicalization_version,
                         year, market, make, model, trim, engine, transmission,
                         drivetrain, identity_source, verification_status)
                    VALUES (%s, %s, %s, 2, 2009, 'US', 'Fixture', 'Domain', 'Exact',
                            '1.3L I4 HYBRID', 'CVT', 'FWD', 'fixture', 'verified')
                    """,
                    (self.vehicle_id, uuid4().hex * 2, uuid4().hex * 2),
                )
                cursor.execute(
                    """
                    INSERT INTO public.catalog_sources
                        (id, source_key, display_name, source_class,
                         license_status, automation_allowed)
                    VALUES (%s, %s, 'Vehicle domain fixture', 'oem_service', 'approved', false)
                    """,
                    (source_id, source_key),
                )

                claims = [
                    *(
                        (claim_id, "vehicle_structure", normalized_key, payload)
                        for claim_id, normalized_key, payload in structure_payloads
                    ),
                    (
                        self.capacity_claim_id,
                        "vehicle_specification",
                        "specification:engine-oil-capacity",
                        capacity_payload,
                    ),
                ]
                for claim_id, claim_domain, normalized_key, payload in claims:
                    evidence_id = uuid4()
                    cursor.execute(
                        """
                        INSERT INTO public.catalog_verified_evidence
                            (id, staging_record_id, candidate_type, verified_payload,
                             vehicle_identity, source_name, source_type, source_record_id,
                             source_url, raw_sha256, fetched_at, provenance,
                             extraction_method, promoted_by)
                        VALUES (%s, %s, 'mechanical_claim_candidate', %s, %s,
                                %s, 'oem_service', %s, %s, %s, %s, %s,
                                'fixture', 'fixture-reviewer')
                        """,
                        (
                            evidence_id,
                            uuid4(),
                            Jsonb({"mechanical_claim": payload}),
                            Jsonb({"vehicle_configuration_id": str(self.vehicle_id)}),
                            source_key,
                            f"record-{claim_id}",
                            f"https://example.invalid/vehicle-domain/{claim_id}",
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
                        VALUES (%s, %s, %s, %s, %s, 'normal', %s, %s,
                                true, true, 'verified', %s, 'fixture-curator')
                        """,
                        (
                            claim_id,
                            source_id,
                            evidence_id,
                            self.vehicle_id,
                            claim_domain,
                            normalized_key,
                            Jsonb(payload),
                            now,
                        ),
                    )

    async def _publish(self, claim_id: UUID, key: str):
        async with session_factory() as session:
            async with session.begin():
                await session.execute(text(f"SET LOCAL ROLE {MATERIALIZER_ROLE}"))
                return await materialize_vehicle_domain_claim_service(
                    session,
                    claim_id=claim_id,
                    actor="fixture-curator:curator",
                    idempotency_key=key,
                )

    async def test_structure_hierarchy_is_insert_only_and_evidence_backed(self) -> None:
        engine = await self._publish(self.engine_claim_id, f"structure:{uuid4().hex}")
        cooling = await self._publish(self.cooling_claim_id, f"structure:{uuid4().hex}")
        pump = await self._publish(self.pump_claim_id, f"structure:{uuid4().hex}")

        self.assertEqual(engine.canonical_domain, "structure")
        self.assertEqual(pump.record_type, "vehicle_structure_node")
        repeated = await self._publish(self.pump_claim_id, f"structure:{uuid4().hex}")
        self.assertTrue(repeated.idempotent)
        self.assertEqual(repeated.record_id, pump.record_id)

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT child.node_key, child.node_type, parent.node_key
                    FROM public.vehicle_structure_nodes child
                    LEFT JOIN public.vehicle_structure_nodes parent ON parent.id = child.parent_node_id
                    WHERE child.vehicle_configuration_id = %s
                    ORDER BY child.position, child.node_key
                    """,
                    (self.vehicle_id,),
                )
                rows = cursor.fetchall()
                self.assertIn(("engine", "system", None), rows)
                self.assertIn(("engine-cooling", "subsystem", "engine"), rows)
                self.assertIn(("engine-water-pump", "assembly", "engine-cooling"), rows)
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM public.canonical_record_evidence
                    WHERE mechanical_claim_id IN (%s, %s, %s)
                    """,
                    (self.engine_claim_id, self.cooling_claim_id, self.pump_claim_id),
                )
                self.assertEqual(cursor.fetchone()[0], 3)

    async def test_specification_value_is_first_class_and_idempotent(self) -> None:
        first = await self._publish(self.capacity_claim_id, f"specification:{uuid4().hex}")
        self.assertEqual(first.canonical_domain, "specification")
        self.assertEqual(first.record_type, "vehicle_specification_value")
        repeated = await self._publish(
            self.capacity_claim_id,
            f"specification:{uuid4().hex}",
        )
        self.assertTrue(repeated.idempotent)
        self.assertEqual(repeated.record_id, first.record_id)

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT d.specification_key, d.specification_type, d.value_kind,
                           v.application_key, v.nominal_value, v.unit, v.qualifier_key,
                           v.conditions
                    FROM public.vehicle_specification_values v
                    JOIN public.specification_definitions d
                      ON d.id = v.specification_definition_id
                    WHERE v.id = %s
                    """,
                    (first.record_id,),
                )
                row = cursor.fetchone()
                self.assertEqual(row[0], "engine-oil-change-capacity-with-filter")
                self.assertEqual(row[1:4], ("capacity", "scalar", "engine-oil-change"))
                self.assertEqual(str(row[4]), "3.400000")
                self.assertEqual(row[5], "US qt")
                self.assertEqual(row[6], "with-filter")
                self.assertEqual(row[7], {"filter_replaced": True})


if __name__ == "__main__":
    unittest.main()
