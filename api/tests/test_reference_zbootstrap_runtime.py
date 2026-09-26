import os
import unittest
from unittest.mock import patch

from sqlalchemy import func, select

from partgraph.database import session_factory
from partgraph.knowledge.completion_models import RepairDownstreamRequirement
from partgraph.knowledge.models import RepairDefinition
from partgraph.knowledge.reference_fleet_bootstrap import (
    PREVIEW_BRANCH,
    preview_reference_bootstrap_enabled,
    publish_reference_fleet,
)

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
EXPECTED_REFERENCE_REPAIRS = 20


class ReferenceFleetBootstrapRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def test_bootstrap_is_scoped_to_exact_mvp_preview(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VERCEL_ENV": "preview",
                "VERCEL_GIT_COMMIT_REF": PREVIEW_BRANCH,
            },
            clear=False,
        ):
            self.assertTrue(preview_reference_bootstrap_enabled())

        with patch.dict(
            os.environ,
            {
                "VERCEL_ENV": "production",
                "VERCEL_GIT_COMMIT_REF": PREVIEW_BRANCH,
            },
            clear=False,
        ):
            self.assertFalse(preview_reference_bootstrap_enabled())

        with patch.dict(
            os.environ,
            {
                "VERCEL_ENV": "preview",
                "VERCEL_GIT_COMMIT_REF": "main",
            },
            clear=False,
        ):
            self.assertFalse(preview_reference_bootstrap_enabled())

    async def test_reference_fleet_publishes_and_is_idempotent(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        first = await publish_reference_fleet()
        self.assertEqual(first.vehicle_configurations, 5)
        self.assertEqual(first.repair_definitions, EXPECTED_REFERENCE_REPAIRS)
        self.assertGreaterEqual(first.downstream_requirements, 1)

        async with session_factory() as db:
            verified_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(RepairDefinition)
                    .where(RepairDefinition.status == "verified")
                )
                or 0
            )
            downstream_count = int(
                await db.scalar(
                    select(func.count()).select_from(RepairDownstreamRequirement)
                )
                or 0
            )
        self.assertGreaterEqual(verified_count, EXPECTED_REFERENCE_REPAIRS)
        self.assertGreaterEqual(downstream_count, 1)

        second = await publish_reference_fleet()
        self.assertEqual(second.repair_definitions, EXPECTED_REFERENCE_REPAIRS)
        self.assertGreaterEqual(second.downstream_requirements, 1)
        self.assertTrue(second.already_complete)

        async with session_factory() as db:
            verified_count_after = int(
                await db.scalar(
                    select(func.count())
                    .select_from(RepairDefinition)
                    .where(RepairDefinition.status == "verified")
                )
                or 0
            )
            downstream_count_after = int(
                await db.scalar(
                    select(func.count()).select_from(RepairDownstreamRequirement)
                )
                or 0
            )
        self.assertEqual(verified_count_after, verified_count)
        self.assertEqual(downstream_count_after, downstream_count)


if __name__ == "__main__":
    unittest.main()
