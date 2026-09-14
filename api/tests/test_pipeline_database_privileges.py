import os
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from partgraph.database import session_factory
from partgraph.knowledge.claim_publication import VerifiedMechanicalClaimSpec, _conflict_record
from partgraph.knowledge.conflict_resolution import (
    CanonicalConflictResolutionCreate,
    resolve_canonical_conflict,
)
from partgraph.knowledge.source_policy import ClaimDomain

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"
CONTRIBUTOR_ROLE = "partgraph_contributor"
CURATOR_ROLE = "partgraph_curator"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class PipelineDatabasePrivilegeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")
        cls.connection = psycopg.connect(_database_url())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.connection.close()

    def _table_privilege(self, role: str, table: str, privilege: str) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_table_privilege(%s, %s, %s)",
                (role, table, privilege),
            )
            row = cursor.fetchone()
            assert row is not None
            return bool(row[0])

    def _column_privilege(
        self,
        role: str,
        table: str,
        column: str,
        privilege: str,
    ) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_column_privilege(%s, %s, %s, %s)",
                (role, table, column, privilege),
            )
            row = cursor.fetchone()
            assert row is not None
            return bool(row[0])

    def test_authenticated_transaction_can_narrow_to_pipeline_roles(self) -> None:
        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {APP_ROLE}")
                cursor.execute(f"SET LOCAL ROLE {CONTRIBUTOR_ROLE}")
                cursor.execute("SELECT current_user")
                self.assertEqual(cursor.fetchone()[0], CONTRIBUTOR_ROLE)

        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {APP_ROLE}")
                cursor.execute(f"SET LOCAL ROLE {CURATOR_ROLE}")
                cursor.execute("SELECT current_user")
                self.assertEqual(cursor.fetchone()[0], CURATOR_ROLE)

    def test_contributor_is_staging_write_only(self) -> None:
        self.assertTrue(
            self._table_privilege(CONTRIBUTOR_ROLE, "public.catalog_sources", "SELECT")
        )
        self.assertTrue(
            self._table_privilege(CONTRIBUTOR_ROLE, "public.vehicle_configurations", "SELECT")
        )
        self.assertTrue(
            self._table_privilege(
                CONTRIBUTOR_ROLE,
                "catalog_staging.ingestion_batches",
                "INSERT",
            )
        )
        self.assertTrue(
            self._table_privilege(
                CONTRIBUTOR_ROLE,
                "catalog_staging.source_records",
                "INSERT",
            )
        )
        self.assertFalse(
            self._table_privilege(
                CONTRIBUTOR_ROLE,
                "catalog_staging.source_records",
                "SELECT",
            )
        )
        self.assertFalse(
            self._table_privilege(
                CONTRIBUTOR_ROLE,
                "public.catalog_verified_evidence",
                "INSERT",
            )
        )
        self.assertFalse(
            self._table_privilege(
                CONTRIBUTOR_ROLE,
                "public.mechanical_claims",
                "INSERT",
            )
        )
        self.assertFalse(
            self._table_privilege(
                CONTRIBUTOR_ROLE,
                "public.part_fitments",
                "INSERT",
            )
        )

    def test_reviewer_still_stops_at_verified_evidence(self) -> None:
        self.assertTrue(
            self._table_privilege(
                REVIEWER_ROLE,
                "public.catalog_verified_evidence",
                "INSERT",
            )
        )
        self.assertFalse(
            self._table_privilege(REVIEWER_ROLE, "public.mechanical_claims", "INSERT")
        )
        self.assertFalse(
            self._table_privilege(REVIEWER_ROLE, "public.canonical_conflicts", "INSERT")
        )

    def test_curator_can_publish_claims_and_resolve_conflicts_only(self) -> None:
        self.assertTrue(
            self._table_privilege(
                CURATOR_ROLE,
                "public.catalog_verified_evidence",
                "SELECT",
            )
        )
        self.assertTrue(
            self._table_privilege(CURATOR_ROLE, "public.mechanical_claims", "INSERT")
        )
        for column in ("promotion_state", "reviewed_at", "reviewed_by", "superseded_by_id"):
            with self.subTest(table="mechanical_claims", column=column):
                self.assertTrue(
                    self._column_privilege(
                        CURATOR_ROLE,
                        "public.mechanical_claims",
                        column,
                        "UPDATE",
                    )
                )

        self.assertTrue(
            self._table_privilege(CURATOR_ROLE, "public.canonical_conflicts", "INSERT")
        )
        self.assertTrue(
            self._table_privilege(
                CURATOR_ROLE,
                "public.canonical_conflict_items",
                "INSERT",
            )
        )
        for column in (
            "conflict_state",
            "resolution",
            "resolution_rationale",
            "resolved_at",
            "resolved_by",
        ):
            with self.subTest(table="canonical_conflicts", column=column):
                self.assertTrue(
                    self._column_privilege(
                        CURATOR_ROLE,
                        "public.canonical_conflicts",
                        column,
                        "UPDATE",
                    )
                )
        self.assertTrue(
            self._column_privilege(
                CURATOR_ROLE,
                "public.canonical_conflict_items",
                "disposition",
                "UPDATE",
            )
        )

        # Conflict resolution must not become a broad table-update grant.
        self.assertFalse(
            self._column_privilege(
                CURATOR_ROLE,
                "public.mechanical_claims",
                "claim_payload",
                "UPDATE",
            )
        )
        self.assertFalse(
            self._column_privilege(
                CURATOR_ROLE,
                "public.canonical_conflicts",
                "conflict_key",
                "UPDATE",
            )
        )
        self.assertFalse(
            self._column_privilege(
                CURATOR_ROLE,
                "public.canonical_conflict_items",
                "mechanical_claim_id",
                "UPDATE",
            )
        )

        for table in (
            "public.vehicle_configurations",
            "public.part_identities",
            "public.part_fitments",
            "public.requirement_definitions",
            "public.repair_definitions",
            "public.repair_operations",
            "public.procedure_actions",
            "public.material_definitions",
            "public.specification_definitions",
        ):
            with self.subTest(table=table):
                self.assertFalse(self._table_privilege(CURATOR_ROLE, table, "INSERT"))
                self.assertFalse(self._table_privilege(CURATOR_ROLE, table, "DELETE"))

        self.assertFalse(
            self._table_privilege(
                CURATOR_ROLE,
                "public.canonical_record_versions",
                "INSERT",
            )
        )
        self.assertFalse(
            self._table_privilege(
                CURATOR_ROLE,
                "public.catalog_verified_evidence",
                "UPDATE",
            )
        )


class PipelineConflictLifecycleTests(unittest.IsolatedAsyncioTestCase):
    source_id: UUID
    evidence_ids: list[UUID]
    claim_ids: list[UUID]
    conflict_id: UUID
    conflict_key: str

    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        self.source_id = uuid4()
        self.evidence_ids = [uuid4(), uuid4(), uuid4()]
        self.claim_ids = [uuid4(), uuid4(), uuid4()]
        self.conflict_id = uuid4()
        self.conflict_key = f"mechanical:test:{uuid4().hex}"
        now = datetime.now(UTC)

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.catalog_sources
                        (id, source_key, display_name, source_class, license_status, automation_allowed)
                    VALUES (%s, %s, %s, 'oem_service', 'approved', false)
                    """,
                    (
                        self.source_id,
                        f"conflict-test-{self.source_id.hex}",
                        "Conflict lifecycle test source",
                    ),
                )
                for index, evidence_id in enumerate(self.evidence_ids[:2], start=1):
                    cursor.execute(
                        """
                        INSERT INTO public.catalog_verified_evidence
                            (id, staging_record_id, candidate_type, verified_payload,
                             source_name, source_type, source_record_id, source_url,
                             raw_sha256, fetched_at, provenance, extraction_method, promoted_by)
                        VALUES (%s, %s, 'mechanical_claim_candidate', %s,
                                %s, 'oem_service', %s, %s,
                                %s, %s, %s, 'fixture', 'fixture-reviewer')
                        """,
                        (
                            evidence_id,
                            uuid4(),
                            Jsonb({"mechanical_claim": {"value": index}}),
                            f"conflict-test-{self.source_id.hex}",
                            f"record-{index}",
                            f"https://example.invalid/conflict/{index}",
                            str(index) * 64,
                            now,
                            Jsonb({"fixture": True}),
                        ),
                    )
                for index, (claim_id, evidence_id) in enumerate(
                    zip(self.claim_ids[:2], self.evidence_ids[:2], strict=True),
                    start=1,
                ):
                    cursor.execute(
                        """
                        INSERT INTO public.mechanical_claims
                            (id, source_id, verified_evidence_id, claim_domain, claim_risk,
                             normalized_key, repair_key, claim_payload, explicit_claim,
                             exact_applicability, promotion_state, conflict_key)
                        VALUES (%s, %s, %s, 'repair_requirement', 'normal',
                                'fixture.requirement', 'fixture.repair', %s, true,
                                true, 'conflict', %s)
                        """,
                        (
                            claim_id,
                            self.source_id,
                            evidence_id,
                            Jsonb({"value": index}),
                            self.conflict_key,
                        ),
                    )
                cursor.execute(
                    """
                    INSERT INTO public.canonical_conflicts
                        (id, conflict_key, canonical_domain, conflict_state)
                    VALUES (%s, %s, 'requirement', 'open')
                    """,
                    (self.conflict_id, self.conflict_key),
                )
                for claim_id in self.claim_ids[:2]:
                    cursor.execute(
                        """
                        INSERT INTO public.canonical_conflict_items
                            (id, conflict_id, mechanical_claim_id, disposition)
                        VALUES (%s, %s, %s, 'contender')
                        """,
                        (uuid4(), self.conflict_id, claim_id),
                    )
            connection.commit()

    async def asyncTearDown(self) -> None:
        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM public.canonical_conflict_items WHERE conflict_id = %s",
                    (self.conflict_id,),
                )
                cursor.execute(
                    "DELETE FROM public.canonical_conflicts WHERE id = %s",
                    (self.conflict_id,),
                )
                cursor.execute(
                    "DELETE FROM public.mechanical_claims WHERE id = ANY(%s)",
                    (self.claim_ids,),
                )
                cursor.execute(
                    "DELETE FROM public.catalog_verified_evidence WHERE id = ANY(%s)",
                    (self.evidence_ids,),
                )
                cursor.execute(
                    "DELETE FROM public.catalog_sources WHERE id = %s",
                    (self.source_id,),
                )
            connection.commit()

    async def test_resolve_then_reopen_claim_conflict(self) -> None:
        actor = SimpleNamespace(id=uuid4(), role="curator")
        request = CanonicalConflictResolutionCreate(
            resolution="accepted_evidence",
            selected_claim_id=self.claim_ids[0],
            rationale="fixture curator selected the supported contender",
        )
        async with session_factory() as db:
            async with db.begin():
                resolved = await resolve_canonical_conflict(
                    self.conflict_id,
                    request,
                    actor,  # type: ignore[arg-type]
                    db,
                )
        self.assertEqual(resolved.selected_claim_id, self.claim_ids[0])
        self.assertFalse(resolved.idempotent)

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT conflict_state, resolution FROM public.canonical_conflicts WHERE id = %s",
                    (self.conflict_id,),
                )
                self.assertEqual(cursor.fetchone(), ("resolved", "accepted_evidence"))
                cursor.execute(
                    "SELECT id, promotion_state FROM public.mechanical_claims WHERE id = ANY(%s)",
                    (self.claim_ids[:2],),
                )
                states = dict(cursor.fetchall())
                self.assertEqual(states[self.claim_ids[0]], "verified")
                self.assertEqual(states[self.claim_ids[1]], "rejected")
                cursor.execute(
                    """
                    SELECT mechanical_claim_id, disposition
                    FROM public.canonical_conflict_items
                    WHERE conflict_id = %s
                    """,
                    (self.conflict_id,),
                )
                dispositions = dict(cursor.fetchall())
                self.assertEqual(dispositions[self.claim_ids[0]], "selected")
                self.assertEqual(dispositions[self.claim_ids[1]], "rejected")

                now = datetime.now(UTC)
                cursor.execute(
                    """
                    INSERT INTO public.catalog_verified_evidence
                        (id, staging_record_id, candidate_type, verified_payload,
                         source_name, source_type, source_record_id, source_url,
                         raw_sha256, fetched_at, provenance, extraction_method, promoted_by)
                    VALUES (%s, %s, 'mechanical_claim_candidate', %s,
                            %s, 'oem_service', 'record-3', 'https://example.invalid/conflict/3',
                            %s, %s, %s, 'fixture', 'fixture-reviewer')
                    """,
                    (
                        self.evidence_ids[2],
                        uuid4(),
                        Jsonb({"mechanical_claim": {"value": 3}}),
                        f"conflict-test-{self.source_id.hex}",
                        "3" * 64,
                        now,
                        Jsonb({"fixture": True}),
                    ),
                )
                cursor.execute(
                    """
                    UPDATE public.mechanical_claims
                    SET promotion_state = 'conflict'
                    WHERE id = %s
                    """,
                    (self.claim_ids[0],),
                )
                cursor.execute(
                    """
                    INSERT INTO public.mechanical_claims
                        (id, source_id, verified_evidence_id, claim_domain, claim_risk,
                         normalized_key, repair_key, claim_payload, explicit_claim,
                         exact_applicability, promotion_state, conflict_key)
                    VALUES (%s, %s, %s, 'repair_requirement', 'normal',
                            'fixture.requirement', 'fixture.repair', %s, true,
                            true, 'conflict', %s)
                    """,
                    (
                        self.claim_ids[2],
                        self.source_id,
                        self.evidence_ids[2],
                        Jsonb({"value": 3}),
                        self.conflict_key,
                    ),
                )
            connection.commit()

        spec = VerifiedMechanicalClaimSpec(
            claim_domain=ClaimDomain.REPAIR_REQUIREMENT,
            normalized_key="fixture.requirement",
            claim_payload={"value": 3},
            explicit_claim=True,
            exact_applicability=True,
            repair_key="fixture.repair",
        )
        async with session_factory() as db:
            async with db.begin():
                reopened_id = await _conflict_record(
                    db,
                    spec=spec,
                    conflict_key=self.conflict_key,
                    contender_ids=[self.claim_ids[0], self.claim_ids[2]],
                )
        self.assertEqual(reopened_id, self.conflict_id)

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT conflict_state, resolution, resolution_rationale, resolved_at, resolved_by
                    FROM public.canonical_conflicts
                    WHERE id = %s
                    """,
                    (self.conflict_id,),
                )
                self.assertEqual(cursor.fetchone(), ("open", None, None, None, None))
                cursor.execute(
                    """
                    SELECT mechanical_claim_id, disposition
                    FROM public.canonical_conflict_items
                    WHERE conflict_id = %s
                    """,
                    (self.conflict_id,),
                )
                dispositions = dict(cursor.fetchall())
                self.assertEqual(dispositions[self.claim_ids[0]], "contender")
                self.assertEqual(dispositions[self.claim_ids[1]], "rejected")
                self.assertEqual(dispositions[self.claim_ids[2]], "contender")


if __name__ == "__main__":
    unittest.main()
