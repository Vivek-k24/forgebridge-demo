import os
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import psycopg

from partgraph.database import session_factory
from partgraph.knowledge.extraction import (
    MECHANICAL_CLAIM_CAPABILITY,
    ExtractionError,
    RawProviderRecord,
    extract_and_stage_provider_record,
)
from partgraph.knowledge.nhtsa import (
    NhtsaRecallAdapter,
    NhtsaVehicleQuery,
    build_nhtsa_recall_url,
)

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def _recall_result(
    *,
    campaign: str,
    component: str,
    summary: str,
) -> dict[str, object]:
    return {
        "Manufacturer": "Example Motor Co.",
        "NHTSACampaignNumber": campaign,
        "parkIt": False,
        "parkOutSide": False,
        "overTheAirUpdate": False,
        "NHTSAActionNumber": "EA00001",
        "ReportReceivedDate": "01/02/2026",
        "Component": component,
        "Summary": summary,
        "Consequence": "The condition may increase the risk of a crash.",
        "Remedy": "Dealers will inspect the affected component and replace it if needed.",
        "Notes": "Consumer hotline text that PartGraph does not promote.",
        "ModelYear": "2024",
        "Make": "EXAMPLE",
        "Model": "MODEL X",
        "price": "$999.99",
        "reviews": [{"rating": 5}],
    }


def _raw_record() -> RawProviderRecord:
    return RawProviderRecord(
        source_record_id="recallsByVehicle:2024:Example:Model X",
        source_url=(
            "https://api.nhtsa.gov/recalls/recallsByVehicle"
            "?make=Example&model=Model+X&modelYear=2024"
        ),
        fetched_at=datetime.now(UTC),
        observed_at=datetime.now(UTC),
        raw_payload={
            "Count": 2,
            "Message": "Results returned successfully",
            "results": [
                _recall_result(
                    campaign="26V000001",
                    component="STEERING",
                    summary="A steering component may bind under some conditions.",
                ),
                _recall_result(
                    campaign="26V000002",
                    component="ENGINE",
                    summary="An engine component may fail prematurely.",
                ),
            ],
        },
        provenance={"fixture": True},
    )


class NhtsaRecallAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = NhtsaRecallAdapter()

    def test_url_is_fixed_to_official_nhtsa_vehicle_recall_endpoint(self) -> None:
        url = build_nhtsa_recall_url(
            NhtsaVehicleQuery(2099, " Fixture Make ", " Fixture Model ")
        )
        parsed = urlparse(url)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.hostname, "api.nhtsa.gov")
        self.assertEqual(parsed.path, "/recalls/recallsByVehicle")
        self.assertEqual(
            parse_qs(parsed.query),
            {
                "make": ["Fixture Make"],
                "model": ["Fixture Model"],
                "modelYear": ["2099"],
            },
        )

    def test_adapter_keeps_recall_facts_and_discards_unrelated_fields(self) -> None:
        candidates = self.adapter.extract(_raw_record())
        self.assertEqual(len(candidates), 2)

        first_claim = candidates[0].candidate_payload["mechanical_claim"]
        self.assertEqual(first_claim["claim_domain"], "safety_campaign")
        self.assertEqual(first_claim["claim_risk"], "safety_critical")
        self.assertTrue(first_claim["explicit_claim"])
        self.assertFalse(first_claim["exact_applicability"])
        self.assertIsNone(first_claim["vehicle_configuration_id"])
        self.assertIsNone(first_claim["repair_key"])

        payload = first_claim["claim_payload"]
        self.assertEqual(payload["campaign_number"], "26V000001")
        self.assertEqual(payload["component"], "STEERING")
        self.assertIn("steering component", payload["issue"])
        self.assertIn("risk of a crash", payload["consequence"])
        self.assertIn("inspect", payload["remedy"])
        self.assertEqual(
            payload["applicability"],
            {
                "market": "US",
                "year": 2024,
                "make": "EXAMPLE",
                "model": "MODEL X",
                "scope": "year_make_model",
            },
        )
        self.assertNotIn("price", payload)
        self.assertNotIn("reviews", payload)
        self.assertNotIn("Notes", payload)

    def test_malformed_response_fails_closed(self) -> None:
        raw = _raw_record()
        raw.raw_payload["Count"] = 3
        with self.assertRaises(ExtractionError):
            self.adapter.extract(raw)

    def test_product_year_boundary_is_enforced(self) -> None:
        with self.assertRaises(ExtractionError):
            NhtsaVehicleQuery(1995, "Fixture Make", "Fixture Model")


class NhtsaRecallDatabaseTests(unittest.IsolatedAsyncioTestCase):
    source_id: UUID
    batch_ids: list[UUID]

    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")
        self.source_id = uuid4()
        self.batch_ids = []
        self.source_key = f"nhtsa-fixture-{self.source_id.hex}"

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.catalog_sources
                        (id, source_key, display_name, source_class,
                         license_status, automation_allowed)
                    VALUES (%s, %s, 'NHTSA collector fixture',
                            'government', 'approved', true)
                    """,
                    (self.source_id, self.source_key),
                )
            connection.commit()

        self.provider = SimpleNamespace(
            id=uuid4(),
            provider_key="nhtsa-fixture-provider",
            provider_kind="vehicle_data",
            enabled=True,
            capabilities=[MECHANICAL_CLAIM_CAPABILITY],
        )
        self.source = SimpleNamespace(
            id=self.source_id,
            source_key=self.source_key,
            source_class="government",
            license_status="approved",
            automation_allowed=True,
        )

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

    async def test_nhtsa_candidates_stage_pending_without_becoming_truth(self) -> None:
        async with session_factory() as db:
            async with db.begin():
                result = await extract_and_stage_provider_record(
                    db,
                    provider=self.provider,
                    source=self.source,
                    adapter=NhtsaRecallAdapter(),
                    record=_raw_record(),
                )
        self.batch_ids.append(result.ingestion_batch_id)
        self.assertEqual(result.inserted_count, 2)
        self.assertEqual(len(result.staging_record_ids), 2)

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT review_status,
                           candidate_payload->'mechanical_claim'->>'claim_domain',
                           candidate_payload->'mechanical_claim'->>'exact_applicability',
                           candidate_payload->'mechanical_claim'->'claim_payload'->>'component'
                    FROM catalog_staging.source_records
                    WHERE id = ANY(%s)
                    ORDER BY id
                    """,
                    (list(result.staging_record_ids),),
                )
                rows = cursor.fetchall()
                self.assertEqual(len(rows), 2)
                self.assertEqual({row[0] for row in rows}, {"pending"})
                self.assertEqual({row[1] for row in rows}, {"safety_campaign"})
                self.assertEqual({row[2] for row in rows}, {"false"})
                self.assertEqual({row[3] for row in rows}, {"ENGINE", "STEERING"})

                cursor.execute(
                    """
                    SELECT count(*)
                    FROM public.catalog_verified_evidence
                    WHERE staging_record_id = ANY(%s)
                    """,
                    (list(result.staging_record_ids),),
                )
                self.assertEqual(cursor.fetchone()[0], 0)

                cursor.execute(
                    """
                    SELECT count(*)
                    FROM public.mechanical_claims mc
                    JOIN public.catalog_verified_evidence e
                      ON e.id = mc.verified_evidence_id
                    WHERE e.staging_record_id = ANY(%s)
                    """,
                    (list(result.staging_record_ids),),
                )
                self.assertEqual(cursor.fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
