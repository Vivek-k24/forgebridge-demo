import json
import os
import tempfile
import unittest
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from partgraph.database import session_factory
from partgraph.knowledge.extraction import MECHANICAL_CLAIM_CAPABILITY
from partgraph.operator.reference_parts import stage_reference_parts_dataset
from partgraph.operator.schemas import ReferencePartsStageRequest

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class OperatorReferencePartsStagingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        self.temp_directory = tempfile.TemporaryDirectory()
        self.reference_root = Path(self.temp_directory.name)
        self.dataset_directory = self.reference_root / "fixture_dataset"
        self.dataset_directory.mkdir()

        self.user_id = uuid4()
        self.provider_id = uuid4()
        self.source_id = uuid4()
        self.binding_id = uuid4()
        self.vehicle_id = uuid4()
        self.batch_ids: list[UUID] = []
        unique = self.binding_id.hex
        self.dataset_key = f"fixture-reviewed-parts-{unique[:12]}"
        self._write_dataset()

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.users
                        (id, email, username, password_hash, role, is_active)
                    VALUES (%s, %s, %s, 'fixture-hash', 'operator_admin', true)
                    """,
                    (
                        self.user_id,
                        f"reference-parts-{unique}@example.invalid",
                        f"refparts_{unique[:20]}",
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO public.vehicle_configurations
                        (id, identity_hash, base_identity_hash,
                         canonicalization_version, year, market, make, model,
                         identity_source, verification_status)
                    VALUES (%s, %s, %s, 3, 2024, 'US', 'Fixture Motors',
                            'MODEL X', 'fixture', 'verified')
                    """,
                    (self.vehicle_id, uuid4().hex * 2, uuid4().hex * 2),
                )
                cursor.execute(
                    """
                    INSERT INTO public.provider_connections
                        (id, provider_key, display_name, provider_kind, enabled,
                         capabilities, created_by, updated_by)
                    VALUES (%s, %s, 'Reference files fixture', 'internal_data',
                            true, %s, %s, %s)
                    """,
                    (
                        self.provider_id,
                        f"reference-files-{unique}",
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
                    VALUES (%s, %s, 'Reviewed parts fixture', 'oem_parts',
                            'approved', true)
                    """,
                    (self.source_id, f"reviewed-parts-{unique}"),
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
        if DATABASE_URL_ENV in os.environ:
            with psycopg.connect(_database_url()) as connection:
                with connection.cursor() as cursor:
                    if self.batch_ids:
                        cursor.execute(
                            "DELETE FROM catalog_staging.ingestion_batches "
                            "WHERE id = ANY(%s)",
                            (self.batch_ids,),
                        )
                    cursor.execute(
                        "DELETE FROM public.operator_audit_events "
                        "WHERE actor_user_id = %s",
                        (self.user_id,),
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
                    cursor.execute(
                        "DELETE FROM public.vehicle_configurations WHERE id = %s",
                        (self.vehicle_id,),
                    )
                    cursor.execute(
                        "DELETE FROM public.users WHERE id = %s",
                        (self.user_id,),
                    )
                connection.commit()
        self.temp_directory.cleanup()

    def _write_dataset(self) -> None:
        manifest = {
            "schema_version": 1,
            "dataset_key": self.dataset_key,
            "vehicle": {
                "vehicle_configuration_id": str(self.vehicle_id),
                "market": "US",
                "year": 2024,
                "make": "Fixture Motors",
                "model": "MODEL X",
            },
            "review": {
                "status": "approved_for_mvp_reference",
                "reviewed_on": "2026-09-14",
                "reviewed_by": "fixture_reviewer",
                "note": "Synthetic reviewed fixture.",
            },
            "publication": {
                "part_manufacturer": "Fixture Motors",
                "claim_risk": "safety_critical",
                "note": "Synthetic conservative risk classification.",
            },
            "sources": [
                {
                    "key": "fixture_catalog_page",
                    "source_class": "oem_parts",
                    "url": "https://example.invalid/fixture-catalog",
                }
            ],
            "component_files": {
                "cooling": {"path": "cooling.json", "count": 2}
            },
        }
        components = [
            {
                "system": "cooling",
                "subsystem": "fixture_loop",
                "name": "Fixture radiator",
                "oem_part_number": "FIX-RAD-1",
                "source_ref": "fixture_catalog_page",
                "fitment_status": "verified",
            },
            {
                "system": "cooling",
                "subsystem": "fixture_loop",
                "name": "Fixture fan",
                "oem_part_number": "FIX-FAN-2",
                "source_ref": "fixture_catalog_page",
                "fitment_status": "verified",
            },
        ]
        (self.dataset_directory / "manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        (self.dataset_directory / "cooling.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "dataset_key": self.dataset_key,
                    "system": "cooling",
                    "components": components,
                }
            ),
            encoding="utf-8",
        )

    async def _stage(self):
        payload = ReferencePartsStageRequest(
            dataset_key=self.dataset_key,
            binding_ids={"oem_parts": self.binding_id},
        )
        async with session_factory() as session:
            async with session.begin():
                return await stage_reference_parts_dataset(
                    session,
                    actor_id=self.user_id,
                    payload=payload,
                    reference_root=self.reference_root,
                )

    async def test_operator_action_stages_pending_candidates_only(self) -> None:
        result = await self._stage()
        self.batch_ids.extend(result.ingestion_batch_ids)
        self.assertEqual(result.source_record_count, 1)
        self.assertEqual(result.candidate_count, 2)
        self.assertEqual(result.inserted_count, 2)

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT review_status,
                           candidate_payload->'mechanical_claim'->>'claim_domain',
                           candidate_payload->'mechanical_claim'->>'exact_applicability',
                           provenance->>'provider_source_binding_id'
                    FROM catalog_staging.source_records
                    WHERE id = ANY(%s)
                    ORDER BY id
                    """,
                    (result.staging_record_ids,),
                )
                rows = cursor.fetchall()
                self.assertEqual(len(rows), 2)
                self.assertTrue(all(row[0] == "pending" for row in rows))
                self.assertTrue(all(row[1] == "part_fitment" for row in rows))
                self.assertTrue(all(row[2] == "true" for row in rows))
                self.assertTrue(
                    all(row[3] == str(self.binding_id) for row in rows)
                )
                cursor.execute(
                    """
                    SELECT count(*)
                    FROM public.catalog_verified_evidence
                    WHERE staging_record_id = ANY(%s)
                    """,
                    (result.staging_record_ids,),
                )
                self.assertEqual(cursor.fetchone()[0], 0)
                cursor.execute(
                    """
                    SELECT count(*)
                    FROM public.operator_audit_events
                    WHERE actor_user_id = %s
                      AND action = 'reference_parts_dataset_staged'
                      AND target_id = %s
                    """,
                    (self.user_id, self.binding_id),
                )
                self.assertEqual(cursor.fetchone()[0], 1)

    async def test_identical_rerun_is_candidate_idempotent(self) -> None:
        first = await self._stage()
        self.batch_ids.extend(first.ingestion_batch_ids)
        second = await self._stage()
        self.batch_ids.extend(second.ingestion_batch_ids)
        self.assertEqual(first.inserted_count, 2)
        self.assertEqual(second.inserted_count, 0)
        self.assertEqual(
            set(first.staging_record_ids),
            set(second.staging_record_ids),
        )


if __name__ == "__main__":
    unittest.main()
