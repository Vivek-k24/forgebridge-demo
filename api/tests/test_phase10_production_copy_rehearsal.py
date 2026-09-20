import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/production-copy-rehearsal.yml"


class Phase10ProductionCopyRehearsalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_rehearsal_is_manual_only(self) -> None:
        self.assertIn("\n  workflow_dispatch:\n", self.workflow)
        self.assertNotIn("\n  pull_request:", self.workflow)
        self.assertNotIn("\n  push:", self.workflow)

    def test_rehearsal_creates_new_expiring_child_of_production(self) -> None:
        self.assertIn("NEON_PRODUCTION_BRANCH: production", self.workflow)
        self.assertIn(
            "neondatabase/create-branch-action@"
            "fb620d43d4c565abaf088b848a4e28e5c4ea4d9c",
            self.workflow,
        )
        self.assertIn("parent_branch: ${{ env.NEON_PRODUCTION_BRANCH }}", self.workflow)
        self.assertIn("expires_at: ${{ env.EXPIRES_AT }}", self.workflow)
        self.assertIn('test "$COPY_CREATED" = "true"', self.workflow)

    def test_rehearsal_uses_copied_data_without_synthetic_seeding(self) -> None:
        self.assertIn(
            "verify_production_copy_upgrade.py snapshot",
            self.workflow,
        )
        self.assertIn(
            "verify_production_copy_upgrade.py verify",
            self.workflow,
        )
        self.assertNotIn("verify_persisted_history_upgrade.py seed", self.workflow)
        self.assertNotIn("Synthetic", self.workflow)

    def test_only_created_copy_receives_database_migration(self) -> None:
        copy_url = (
            "PARTGRAPH_DATABASE_URL: "
            "${{ steps.create-production-copy.outputs.db_url }}"
        )
        self.assertGreaterEqual(self.workflow.count(copy_url), 3)
        self.assertIn("alembic -c api/alembic.ini upgrade head", self.workflow)
        self.assertNotIn("PARTGRAPH_PRODUCTION_DATABASE_URL", self.workflow)
        self.assertNotIn("alembic downgrade", self.workflow)

    def test_rehearsal_retains_non_sensitive_validation_evidence(self) -> None:
        self.assertIn("test_mvp_migrations.py", self.workflow)
        self.assertIn("phase10-production-copy-fingerprint-", self.workflow)
        self.assertIn("Production mutated: **no**", self.workflow)


if __name__ == "__main__":
    unittest.main()
