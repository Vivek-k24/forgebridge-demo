import os
import unittest

import psycopg
from sqlalchemy import text

from partgraph.database import session_factory
from partgraph.knowledge.source_policy import (
    ClaimDomain,
    ClaimRisk,
    PromotionDecision,
    SourceClass,
    assess_mechanical_claim,
    load_source_authority_policy,
)

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
CURATOR_ROLE = "partgraph_curator"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class SourceAuthorityPolicyDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")
        cls.connection = psycopg.connect(_database_url())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.connection.close()

    def _table_privilege(self, privilege: str) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_table_privilege(%s, %s, %s)",
                (CURATOR_ROLE, "public.source_authority_policies", privilege),
            )
            row = cursor.fetchone()
            assert row is not None
            return bool(row[0])

    def test_claim_policy_matrix_is_complete_and_unique(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*)
                FROM public.source_authority_policies
                WHERE claim_domain IS NOT NULL
                  AND policy_key LIKE 'claim.%'
                """
            )
            self.assertEqual(cursor.fetchone()[0], 70)
            cursor.execute(
                """
                SELECT count(*)
                FROM (
                    SELECT claim_domain, source_class, risk_class
                    FROM public.source_authority_policies
                    WHERE claim_domain IS NOT NULL
                    GROUP BY claim_domain, source_class, risk_class
                    HAVING count(*) <> 1
                ) AS invalid_scopes
                """
            )
            self.assertEqual(cursor.fetchone()[0], 0)

    def test_seed_preserves_representative_legacy_authority_decisions(self) -> None:
        expected = {
            ("vehicle_identity", "government", "normal"): (
                "vehicle_identity",
                "accepted",
            ),
            ("safety_campaign", "government", "normal"): (None, "conditional"),
            ("repair_procedure", "oem_service", "normal"): (
                "procedure",
                "accepted",
            ),
            ("repair_requirement", "oem_service", "safety_critical"): (
                "requirement",
                "conditional",
            ),
            ("repair_procedure", "oem_parts", "normal"): (
                "procedure",
                "rejected",
            ),
            ("part_fitment", "oem_parts", "safety_critical"): (
                "fitment",
                "accepted",
            ),
            ("part_fitment", "retailer", "normal"): ("fitment", "rejected"),
        }
        with self.connection.cursor() as cursor:
            for scope, expected_value in expected.items():
                with self.subTest(scope=scope):
                    cursor.execute(
                        """
                        SELECT canonical_domain, authority_state
                        FROM public.source_authority_policies
                        WHERE claim_domain = %s
                          AND source_class = %s
                          AND risk_class = %s
                        """,
                        scope,
                    )
                    self.assertEqual(cursor.fetchone(), expected_value)

    def test_curator_policy_access_is_read_only(self) -> None:
        self.assertTrue(self._table_privilege("SELECT"))
        self.assertFalse(self._table_privilege("INSERT"))
        self.assertFalse(self._table_privilege("UPDATE"))
        self.assertFalse(self._table_privilege("DELETE"))


class SourceAuthorityPolicyRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_curator_loads_seeded_policy_and_evaluates_it(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        async with session_factory() as db:
            async with db.begin():
                await db.execute(text(f"SET LOCAL ROLE {CURATOR_ROLE}"))
                policy = await load_source_authority_policy(
                    db,
                    source_class=SourceClass.OEM_SERVICE,
                    claim_domain=ClaimDomain.REPAIR_PROCEDURE,
                    risk=ClaimRisk.NORMAL,
                )
                self.assertIsNotNone(policy)
                assessment = assess_mechanical_claim(
                    policy=policy,
                    source_class=SourceClass.OEM_SERVICE,
                    claim_domain=ClaimDomain.REPAIR_PROCEDURE,
                    exact_applicability=True,
                    explicit_claim=True,
                )
        self.assertEqual(assessment.decision, PromotionDecision.ELIGIBLE)

    async def test_safety_campaign_policy_has_no_fake_canonical_domain(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        async with session_factory() as db:
            async with db.begin():
                await db.execute(text(f"SET LOCAL ROLE {CURATOR_ROLE}"))
                policy = await load_source_authority_policy(
                    db,
                    source_class=SourceClass.GOVERNMENT,
                    claim_domain=ClaimDomain.SAFETY_CAMPAIGN,
                    risk=ClaimRisk.NORMAL,
                )
                self.assertIsNotNone(policy)
                assert policy is not None
                self.assertIsNone(policy.canonical_domain)
                assessment = assess_mechanical_claim(
                    policy=policy,
                    source_class=SourceClass.GOVERNMENT,
                    claim_domain=ClaimDomain.SAFETY_CAMPAIGN,
                    exact_applicability=True,
                    explicit_claim=True,
                )
        self.assertEqual(
            assessment.decision,
            PromotionDecision.HUMAN_REVIEW_REQUIRED,
        )


if __name__ == "__main__":
    unittest.main()
