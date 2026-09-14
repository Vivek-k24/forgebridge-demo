import os
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from partgraph.database import session_factory
from partgraph.errors import ErrorCode, PartGraphError
from partgraph.knowledge.conflict_resolution import (
    CanonicalConflictResolutionCreate,
    resolve_canonical_conflict,
)
from partgraph.knowledge.source_policy import (
    ClaimDomain,
    ClaimRisk,
    PromotionDecision,
    SourceClass,
    assess_mechanical_claim,
)

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class SourceAuthorityFailClosedTests(unittest.TestCase):
    def test_minimum_evidence_count_cannot_be_satisfied_by_curator_review(self) -> None:
        policy = SimpleNamespace(
            claim_domain=ClaimDomain.REPAIR_REQUIREMENT.value,
            canonical_domain="requirement",
            source_class=SourceClass.OEM_SERVICE.value,
            risk_class=ClaimRisk.NORMAL.value,
            authority_state="accepted",
            requires_exact_applicability=True,
            minimum_evidence_count=2,
            rationale="fixture requires two independent evidence records",
        )
        assessment = assess_mechanical_claim(
            policy=policy,
            source_class=SourceClass.OEM_SERVICE,
            claim_domain=ClaimDomain.REPAIR_REQUIREMENT,
            exact_applicability=True,
            explicit_claim=True,
            evidence_count=1,
        )
        self.assertEqual(assessment.decision, PromotionDecision.CANDIDATE_ONLY)


class ConflictAuthorityEnforcementTests(unittest.IsolatedAsyncioTestCase):
    source_id: UUID
    evidence_ids: list[UUID]
    claim_ids: list[UUID]
    conflict_id: UUID
    conflict_key: str

    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        self.source_id = uuid4()
        self.evidence_ids = [uuid4(), uuid4()]
        self.claim_ids = [uuid4(), uuid4()]
        self.conflict_id = uuid4()
        self.conflict_key = f"mechanical:authority-test:{uuid4().hex}"
        source_key = f"authority-test-{self.source_id.hex}"
        now = datetime.now(UTC)

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.catalog_sources
                        (id, source_key, display_name, source_class,
                         license_status, automation_allowed)
                    VALUES (%s, %s, 'Authority enforcement fixture',
                            'retailer', 'approved', false)
                    """,
                    (self.source_id, source_key),
                )
                for index, evidence_id in enumerate(self.evidence_ids, start=1):
                    cursor.execute(
                        """
                        INSERT INTO public.catalog_verified_evidence
                            (id, staging_record_id, candidate_type, verified_payload,
                             source_name, source_type, source_record_id, source_url,
                             raw_sha256, fetched_at, provenance,
                             extraction_method, promoted_by)
                        VALUES (%s, %s, 'mechanical_claim_candidate', %s,
                                %s, 'retailer', %s, %s,
                                %s, %s, %s, 'fixture', 'fixture-reviewer')
                        """,
                        (
                            evidence_id,
                            uuid4(),
                            Jsonb({"mechanical_claim": {"value": index}}),
                            source_key,
                            f"record-{index}",
                            f"https://example.invalid/authority/{index}",
                            str(index) * 64,
                            now,
                            Jsonb({"fixture": True}),
                        ),
                    )
                for index, (claim_id, evidence_id) in enumerate(
                    zip(self.claim_ids, self.evidence_ids, strict=True),
                    start=1,
                ):
                    cursor.execute(
                        """
                        INSERT INTO public.mechanical_claims
                            (id, source_id, verified_evidence_id, claim_domain,
                             claim_risk, normalized_key, repair_key, claim_payload,
                             explicit_claim, exact_applicability,
                             promotion_state, conflict_key)
                        VALUES (%s, %s, %s, 'repair_requirement', 'normal',
                                'fixture.authority', 'fixture.repair', %s,
                                true, true, 'conflict', %s)
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
                for claim_id in self.claim_ids:
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
        if DATABASE_URL_ENV not in os.environ:
            return
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

    async def test_candidate_only_source_cannot_win_conflict_resolution(self) -> None:
        actor = SimpleNamespace(id=uuid4(), role="curator")
        request = CanonicalConflictResolutionCreate(
            resolution="accepted_evidence",
            selected_claim_id=self.claim_ids[0],
            rationale="fixture attempt to select retailer evidence",
        )
        with self.assertRaises(PartGraphError) as context:
            async with session_factory() as db:
                async with db.begin():
                    await resolve_canonical_conflict(
                        self.conflict_id,
                        request,
                        actor,  # type: ignore[arg-type]
                        db,
                    )
        self.assertEqual(
            context.exception.code,
            ErrorCode.KNOWLEDGE_CONFLICT_RESOLUTION_INVALID,
        )

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT conflict_state, resolution FROM public.canonical_conflicts WHERE id = %s",
                    (self.conflict_id,),
                )
                self.assertEqual(cursor.fetchone(), ("open", None))
                cursor.execute(
                    """
                    SELECT promotion_state
                    FROM public.mechanical_claims
                    WHERE id = ANY(%s)
                    ORDER BY id
                    """,
                    (self.claim_ids,),
                )
                self.assertEqual(
                    [row[0] for row in cursor.fetchall()],
                    ["conflict", "conflict"],
                )


if __name__ == "__main__":
    unittest.main()
