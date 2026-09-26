import os
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg

from partgraph.database import session_factory
from partgraph.knowledge.extraction import (
    MECHANICAL_CLAIM_CAPABILITY,
    ExtractionError,
    RawProviderRecord,
    StructuredMechanicalClaimAdapter,
    _validate_execution_boundary,
    extract_and_stage_provider_record,
)

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def _raw_record(*, configuration_id: UUID | None) -> RawProviderRecord:
    return RawProviderRecord(
        source_record_id="structured-record-1",
        source_url="https://example.invalid/structured-record-1",
        fetched_at=datetime.now(UTC),
        raw_payload={
            "claims": [
                {
                    "claim_domain": "repair_requirement",
                    "normalized_key": " requirement.socket-10mm ",
                    "claim_payload": {
                        "requirement_key": "tool.socket-10mm",
                        "category": "tool",
                    },
                    "explicit_claim": True,
                    "exact_applicability": True,
                    "vehicle_configuration_id": (
                        str(configuration_id) if configuration_id is not None else None
                    ),
                    "repair_key": " cover.remove ",
                    "confidence": 0.98,
                },
                {
                    "claim_domain": "repair_procedure",
                    "normalized_key": " procedure.remove-cover ",
                    "claim_payload": {
                        "action_key": "remove-cover",
                        "title": "Remove cover",
                        "instruction": "Remove the cover fasteners.",
                    },
                    "explicit_claim": True,
                    "exact_applicability": True,
                    "vehicle_configuration_id": (
                        str(configuration_id) if configuration_id is not None else None
                    ),
                    "repair_key": " cover.remove ",
                    "confidence": 0.96,
                },
            ]
        },
        provenance={"fixture": True},
    )


class StructuredMechanicalClaimAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = StructuredMechanicalClaimAdapter()

    def test_one_raw_record_can_emit_multiple_normalized_candidates(self) -> None:
        configuration_id = uuid4()
        candidates = self.adapter.extract(
            _raw_record(configuration_id=configuration_id)
        )
        self.assertEqual(len(candidates), 2)
        self.assertEqual(
            {item.candidate_type for item in candidates},
            {"mechanical_claim_candidate"},
        )
        requirement = candidates[0].candidate_payload["mechanical_claim"]
        self.assertEqual(requirement["normalized_key"], "requirement.socket-10mm")
        self.assertEqual(requirement["repair_key"], "cover.remove")
        self.assertEqual(requirement["vehicle_configuration_id"], str(configuration_id))

    def test_exact_claim_without_vehicle_configuration_fails_closed(self) -> None:
        with self.assertRaises(ExtractionError):
            self.adapter.extract(_raw_record(configuration_id=None))

    def test_repair_claim_without_repair_key_is_rejected(self) -> None:
        raw = _raw_record(configuration_id=uuid4())
        raw.raw_payload["claims"][0]["repair_key"] = "   "  # type: ignore[index]
        with self.assertRaises(ExtractionError):
            self.adapter.extract(raw)

    def test_disabled_or_ineligible_execution_boundary_is_rejected(self) -> None:
        provider = SimpleNamespace(
            id=uuid4(),
            provider_key="fixture-provider",
            provider_kind="internal_data",
            enabled=False,
            capabilities=[MECHANICAL_CLAIM_CAPABILITY],
        )
        source = SimpleNamespace(
            id=uuid4(),
            source_key="fixture-source",
            source_class="oem_service",
            license_status="approved",
            automation_allowed=True,
        )
        with self.assertRaises(ExtractionError):
            _validate_execution_boundary(
                provider=provider,
                source=source,
                adapter=self.adapter,
            )

        provider.enabled = True
        provider.capabilities = []
        with self.assertRaises(ExtractionError):
            _validate_execution_boundary(
                provider=provider,
                source=source,
                adapter=self.adapter,
            )

        provider.capabilities = [MECHANICAL_CLAIM_CAPABILITY]
        source.license_status = "prohibited"
        with self.assertRaises(ExtractionError):
            _validate_execution_boundary(
                provider=provider,
                source=source,
                adapter=self.adapter,
            )

        source.license_status = "approved"
        source.automation_allowed = False
        with self.assertRaises(ExtractionError):
            _validate_execution_boundary(
                provider=provider,
                source=source,
                adapter=self.adapter,
            )


class ExtractionPipelineDatabaseTests(unittest.IsolatedAsyncioTestCase):
    source_id: UUID
    batch_ids: list[UUID]
    staging_record_ids: list[UUID]

    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")
        self.source_id = uuid4()
        self.batch_ids = []
        self.staging_record_ids = []
        self.source_key = f"extraction-fixture-{self.source_id.hex}"

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
                    INSERT INTO public.catalog_sources
                        (id, source_key, display_name, source_class,
                         license_status, automation_allowed)
                    VALUES (%s, %s, 'Extraction fixture source',
                            'oem_service', 'approved', true)
                    """,
                    (self.source_id, self.source_key),
                )
            connection.commit()

        self.provider = SimpleNamespace(
            id=uuid4(),
            provider_key="fixture-structured-provider",
            provider_kind="internal_data",
            enabled=True,
            capabilities=[MECHANICAL_CLAIM_CAPABILITY],
        )
        self.source = SimpleNamespace(
            id=self.source_id,
            source_key=self.source_key,
            source_class="oem_service",
            license_status="approved",
            automation_allowed=True,
        )
        self.adapter = StructuredMechanicalClaimAdapter()

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
                    "DELETE FROM public.catalog_sources WHERE id = %s",
                    (self.source_id,),
                )
            connection.commit()

    async def test_multi_candidate_staging_is_pending_and_idempotent(self) -> None:
        raw = _raw_record(configuration_id=self.vehicle_configuration_id)
        async with session_factory() as db:
            async with db.begin():
                first = await extract_and_stage_provider_record(
                    db,
                    provider=self.provider,
                    source=self.source,
                    adapter=self.adapter,
                    record=raw,
                )
        self.batch_ids.append(first.ingestion_batch_id)
        self.staging_record_ids.extend(first.staging_record_ids)
        self.assertEqual(first.inserted_count, 2)
        self.assertEqual(len(set(first.staging_record_ids)), 2)

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT raw_sha256, dedupe_key, review_status,
                           vehicle_identity->>'vehicle_configuration_id',
                           extraction_method,
                           provenance->>'provider_key'
                    FROM catalog_staging.source_records
                    WHERE id = ANY(%s)
                    ORDER BY id
                    """,
                    (list(first.staging_record_ids),),
                )
                rows = cursor.fetchall()
                self.assertEqual(len(rows), 2)
                self.assertEqual(len({row[0] for row in rows}), 1)
                self.assertEqual(len({row[1] for row in rows}), 2)
                self.assertEqual({row[2] for row in rows}, {"pending"})
                self.assertEqual(
                    {row[3] for row in rows},
                    {str(self.vehicle_configuration_id)},
                )
                self.assertEqual(
                    {row[4] for row in rows},
                    {"structured_mechanical_claims@v1"},
                )
                self.assertEqual(
                    {row[5] for row in rows},
                    {"fixture-structured-provider"},
                )
                cursor.execute(
                    """
                    SELECT count(*)
                    FROM public.catalog_verified_evidence
                    WHERE staging_record_id = ANY(%s)
                    """,
                    (list(first.staging_record_ids),),
                )
                self.assertEqual(cursor.fetchone()[0], 0)

        async with session_factory() as db:
            async with db.begin():
                second = await extract_and_stage_provider_record(
                    db,
                    provider=self.provider,
                    source=self.source,
                    adapter=self.adapter,
                    record=raw,
                )
        self.batch_ids.append(second.ingestion_batch_id)
        self.assertEqual(second.inserted_count, 0)
        self.assertEqual(second.staging_record_ids, first.staging_record_ids)

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*)
                    FROM catalog_staging.source_records
                    WHERE id = ANY(%s)
                    """,
                    (list(first.staging_record_ids),),
                )
                self.assertEqual(cursor.fetchone()[0], 2)
                cursor.execute(
                    """
                    SELECT count(*)
                    FROM public.mechanical_claims mc
                    JOIN public.catalog_verified_evidence e
                      ON e.id = mc.verified_evidence_id
                    WHERE e.staging_record_id = ANY(%s)
                    """,
                    (list(first.staging_record_ids),),
                )
                self.assertEqual(cursor.fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
