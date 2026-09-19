import os
import unittest
from datetime import UTC, datetime
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from partgraph.database import session_factory
from partgraph.knowledge.extraction import (
    MECHANICAL_CLAIM_CAPABILITY,
    ExtractionError,
    RawProviderRecord,
    StructuredMechanicalClaimAdapter,
    extract_and_stage_bound_provider_record,
)

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
INGESTOR_ROLE = "partgraph_ingestor"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def _raw_record(configuration_id: UUID) -> RawProviderRecord:
    return RawProviderRecord(
        source_record_id="bound-record-1",
        source_url="https://example.invalid/bound-record-1",
        fetched_at=datetime.now(UTC),
        raw_payload={
            "claims": [
                {
                    "claim_domain": "repair_requirement",
                    "normalized_key": "requirement.bound-socket",
                    "claim_payload": {
                        "requirement_key": "tool.bound-socket",
                        "category": "tool",
                    },
                    "explicit_claim": True,
                    "exact_applicability": True,
                    "vehicle_configuration_id": str(configuration_id),
                    "repair_key": "fixture.bound-repair",
                    "confidence": 0.99,
                }
            ]
        },
        provenance={"fixture": "provider-source-binding"},
    )


class ProviderSourceBindingPrivilegeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")
        cls.connection = psycopg.connect(_database_url())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.connection.close()

    def _table_privilege(self, table: str, privilege: str) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_table_privilege(%s, %s, %s)",
                (INGESTOR_ROLE, table, privilege),
            )
            row = cursor.fetchone()
            assert row is not None
            return bool(row[0])

    def _column_privilege(self, table: str, column: str, privilege: str) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_column_privilege(%s, %s, %s, %s)",
                (INGESTOR_ROLE, table, column, privilege),
            )
            row = cursor.fetchone()
            assert row is not None
            return bool(row[0])

    def test_ingestor_reads_binding_and_writes_only_staging(self) -> None:
        for table in (
            "public.provider_connections",
            "public.provider_source_bindings",
            "public.catalog_sources",
            "public.vehicle_configurations",
        ):
            with self.subTest(table=table):
                self.assertTrue(self._table_privilege(table, "SELECT"))
                self.assertFalse(self._table_privilege(table, "INSERT"))
                self.assertFalse(self._table_privilege(table, "DELETE"))

        self.assertTrue(
            self._table_privilege("catalog_staging.ingestion_batches", "SELECT")
        )
        self.assertTrue(
            self._table_privilege("catalog_staging.ingestion_batches", "INSERT")
        )
        self.assertTrue(
            self._column_privilege(
                "catalog_staging.ingestion_batches",
                "status",
                "UPDATE",
            )
        )
        self.assertTrue(
            self._table_privilege("catalog_staging.source_records", "SELECT")
        )
        self.assertTrue(
            self._table_privilege("catalog_staging.source_records", "INSERT")
        )
        self.assertFalse(
            self._table_privilege("catalog_staging.source_records", "UPDATE")
        )

        for table in (
            "public.catalog_verified_evidence",
            "public.mechanical_claims",
            "public.canonical_record_versions",
            "public.repair_definitions",
        ):
            with self.subTest(table=table):
                self.assertFalse(self._table_privilege(table, "INSERT"))
                self.assertFalse(self._table_privilege(table, "UPDATE"))
                self.assertFalse(self._table_privilege(table, "DELETE"))


class BoundProviderExtractionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        self.user_id = uuid4()
        self.provider_id = uuid4()
        self.source_id = uuid4()
        self.binding_id = uuid4()
        self.batch_ids: list[UUID] = []
        unique = self.binding_id.hex
        self.provider_key = f"bound-provider-{unique}"
        self.source_key = f"bound-source-{unique}"

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM public.vehicle_configurations ORDER BY id LIMIT 1"
                )
                row = cursor.fetchone()
                assert row is not None
                self.vehicle_configuration_id = row[0]
                cursor.execute(
                    """
                    INSERT INTO public.users
                        (id, email, username, password_hash, role, is_active)
                    VALUES (%s, %s, %s, 'fixture-hash', 'operator_admin', true)
                    """,
                    (
                        self.user_id,
                        f"binding-{unique}@example.invalid",
                        f"bind_{unique[:20]}",
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO public.provider_connections
                        (id, provider_key, display_name, provider_kind, enabled,
                         capabilities, created_by, updated_by)
                    VALUES (%s, %s, 'Bound provider fixture', 'internal_data', true,
                            %s, %s, %s)
                    """,
                    (
                        self.provider_id,
                        self.provider_key,
                        Jsonb([MECHANICAL_CLAIM_CAPABILITY]),
                        self.user_id,
                        self.user_id,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO public.catalog_sources
                        (id, source_key, display_name, source_class,
                         license_status, automation_allowed)
                    VALUES (%s, %s, 'Bound source fixture',
                            'oem_service', 'approved', true)
                    """,
                    (self.source_id, self.source_key),
                )
                cursor.execute(
                    """
                    INSERT INTO public.provider_source_bindings
                        (id, provider_connection_id, source_id, enabled,
                         created_by, updated_by)
                    VALUES (%s, %s, %s, true, %s, %s)
                    """,
                    (
                        self.binding_id,
                        self.provider_id,
                        self.source_id,
                        self.user_id,
                        self.user_id,
                    ),
                )
            connection.commit()

    async def asyncTearDown(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            return
        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                if self.batch_ids:
                    cursor.execute(
                        "DELETE FROM catalog_staging.ingestion_batches WHERE id = ANY(%s)",
                        (self.batch_ids,),
                    )
                cursor.execute(
                    "DELETE FROM public.provider_source_bindings WHERE id = %s",
                    (self.binding_id,),
                )
                cursor.execute(
                    "DELETE FROM public.provider_connections WHERE id = %s",
                    (self.provider_id,),
                )
                cursor.execute(
                    "DELETE FROM public.catalog_sources WHERE id = %s",
                    (self.source_id,),
                )
                cursor.execute("DELETE FROM public.users WHERE id = %s", (self.user_id,))
            connection.commit()

    async def test_bound_execution_stages_pending_candidate_with_binding_provenance(self) -> None:
        async with session_factory() as db:
            async with db.begin():
                result = await extract_and_stage_bound_provider_record(
                    db,
                    binding_id=self.binding_id,
                    adapter=StructuredMechanicalClaimAdapter(),
                    record=_raw_record(self.vehicle_configuration_id),
                )
        self.batch_ids.append(result.ingestion_batch_id)
        self.assertEqual(result.inserted_count, 1)

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT review_status,
                           provenance->>'provider_source_binding_id',
                           provenance->>'provider_connection_id',
                           provenance->>'source_registry_id'
                    FROM catalog_staging.source_records
                    WHERE id = %s
                    """,
                    (result.staging_record_ids[0],),
                )
                row = cursor.fetchone()
                assert row is not None
                self.assertEqual(row[0], "pending")
                self.assertEqual(row[1], str(self.binding_id))
                self.assertEqual(row[2], str(self.provider_id))
                self.assertEqual(row[3], str(self.source_id))
                cursor.execute(
                    "SELECT count(*) FROM public.catalog_verified_evidence WHERE staging_record_id = %s",
                    (result.staging_record_ids[0],),
                )
                self.assertEqual(cursor.fetchone()[0], 0)

    async def test_missing_or_disabled_binding_fails_closed(self) -> None:
        async with session_factory() as db:
            async with db.begin():
                with self.assertRaises(ExtractionError):
                    await extract_and_stage_bound_provider_record(
                        db,
                        binding_id=uuid4(),
                        adapter=StructuredMechanicalClaimAdapter(),
                        record=_raw_record(self.vehicle_configuration_id),
                    )

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.provider_source_bindings SET enabled = false WHERE id = %s",
                    (self.binding_id,),
                )
            connection.commit()

        async with session_factory() as db:
            async with db.begin():
                with self.assertRaises(ExtractionError):
                    await extract_and_stage_bound_provider_record(
                        db,
                        binding_id=self.binding_id,
                        adapter=StructuredMechanicalClaimAdapter(),
                        record=_raw_record(self.vehicle_configuration_id),
                    )


if __name__ == "__main__":
    unittest.main()
