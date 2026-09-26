import os
import unittest
from datetime import UTC, datetime
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from partgraph.database import session_factory
from partgraph.errors import PartGraphError
from partgraph.knowledge.extraction import MECHANICAL_CLAIM_CAPABILITY, RawProviderRecord
from partgraph.operator.nhtsa import stage_nhtsa_recall_query
from partgraph.operator.schemas import NhtsaRecallStageRequest

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class _FixtureCollector:
    async def fetch(self, query):
        moment = datetime.now(UTC)
        return RawProviderRecord(
            source_record_id=(
                f"recallsByVehicle:{query.year}:"
                f"{query.normalized_make}:{query.normalized_model}"
            ),
            source_url=(
                "https://api.nhtsa.gov/recalls/recallsByVehicle"
                f"?make={query.normalized_make}&model={query.normalized_model}"
                f"&modelYear={query.year}"
            ),
            fetched_at=moment,
            observed_at=moment,
            raw_payload={
                "Count": 1,
                "Message": "Results returned successfully",
                "results": [
                    {
                        "Manufacturer": "Example Motor Co.",
                        "NHTSACampaignNumber": "26V000001",
                        "parkIt": False,
                        "parkOutSide": False,
                        "overTheAirUpdate": False,
                        "NHTSAActionNumber": "EA00001",
                        "ReportReceivedDate": "01/02/2026",
                        "Component": "STEERING",
                        "Summary": "A steering component may bind.",
                        "Consequence": "The condition may increase crash risk.",
                        "Remedy": "Dealers will inspect and replace if needed.",
                        "ModelYear": str(query.year),
                        "Make": query.normalized_make,
                        "Model": query.normalized_model,
                    }
                ],
            },
            provenance={"fixture": True},
        )


class OperatorNhtsaIngestionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        self.user_id = uuid4()
        self.provider_id = uuid4()
        self.source_id = uuid4()
        self.binding_id = uuid4()
        self.batch_ids: list[UUID] = []
        unique = self.binding_id.hex

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
                        f"nhtsa-ingest-{unique}@example.invalid",
                        f"nhtsa_ingest_{unique[:18]}",
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO public.provider_connections
                        (id, provider_key, display_name, provider_kind, base_url,
                         enabled, capabilities, created_by, updated_by)
                    VALUES (%s, %s, 'NHTSA fixture', 'vehicle_data',
                            'https://api.nhtsa.gov', true, %s, %s, %s)
                    """,
                    (
                        self.provider_id,
                        f"nhtsa-fixture-{unique}",
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
                    VALUES (%s, 'nhtsa-recalls', 'NHTSA Safety Recalls',
                            'government', 'approved', true)
                    """,
                    (self.source_id,),
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
                    "DELETE FROM public.operator_audit_events WHERE actor_user_id = %s",
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
                    "DELETE FROM public.users WHERE id = %s",
                    (self.user_id,),
                )
            connection.commit()

    async def _stage(self):
        payload = NhtsaRecallStageRequest(
            binding_id=self.binding_id,
            year=2024,
            make=" Example ",
            model=" Model X ",
        )
        async with session_factory() as session:
            async with session.begin():
                return await stage_nhtsa_recall_query(
                    session,
                    actor_id=self.user_id,
                    payload=payload,
                    collector=_FixtureCollector(),
                )

    async def test_operator_query_uses_bound_source_and_stays_pending(self) -> None:
        result = await self._stage()
        self.batch_ids.append(result.ingestion_batch_id)
        self.assertEqual(result.candidate_count, 1)
        self.assertEqual(result.inserted_count, 1)
        self.assertEqual(result.make, "Example")
        self.assertEqual(result.model, "Model X")

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
                    """,
                    (result.staging_record_ids,),
                )
                row = cursor.fetchone()
                self.assertEqual(row[0], "pending")
                self.assertEqual(row[1], "safety_campaign")
                self.assertEqual(row[2], "false")
                self.assertEqual(row[3], str(self.binding_id))

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
                      AND action = 'nhtsa_recall_query_staged'
                      AND target_id = %s
                    """,
                    (self.user_id, self.binding_id),
                )
                self.assertEqual(cursor.fetchone()[0], 1)

    async def test_disabled_binding_fails_closed(self) -> None:
        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.provider_source_bindings SET enabled = false WHERE id = %s",
                    (self.binding_id,),
                )
            connection.commit()

        with self.assertRaises(PartGraphError):
            await self._stage()


if __name__ == "__main__":
    unittest.main()
