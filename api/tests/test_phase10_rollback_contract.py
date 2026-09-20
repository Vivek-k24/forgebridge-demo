import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "ops/cutover/phase10_rollback_v1.json"
MIGRATION_PATH = REPO_ROOT / "api/migrations/versions/0063_photo_storage_outbox.py"
MODEL_PATH = REPO_ROOT / "api/partgraph/repair_experience/memory_models.py"
RUNBOOK_PATH = REPO_ROOT / "docs/DATABASE_MIGRATION_PROMOTION_RUNBOOK.md"


class Phase10RollbackContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        cls.migration = MIGRATION_PATH.read_text(encoding="utf-8")
        cls.model = MODEL_PATH.read_text(encoding="utf-8")
        cls.runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    def test_contract_records_exact_observed_boundary(self) -> None:
        self.assertEqual(
            self.contract["production"]["database_revision"],
            "0020_catalog_coverage",
        )
        self.assertEqual(
            self.contract["migrated_copy"]["database_revision"],
            "0063_photo_storage_outbox",
        )
        comparison = self.contract["baseline_schema_comparison"]
        self.assertEqual(comparison["tables"], 36)
        self.assertEqual(comparison["columns"], 320)
        self.assertEqual(comparison["missing_baseline_columns"], 0)
        self.assertEqual(comparison["changed_baseline_columns"], 0)

    def test_code_only_rollback_is_explicitly_prohibited(self) -> None:
        self.assertFalse(
            self.contract["code_only_rollback_safe_after_schema_promotion"]
        )
        self.assertEqual(
            self.contract["rollback_policy"]["application_only_rollback"],
            "prohibited_after_schema_reaches_0063_or_later_until_compatibility_is_explicitly_reproven",
        )
        self.assertFalse(
            self.contract["rollback_policy"]["automatic_alembic_downgrade"]
        )

    def test_storage_state_is_the_recorded_blocker(self) -> None:
        blockers = self.contract["blocking_changes"]
        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0]["table"], "repair_photo_evidence")
        self.assertEqual(blockers[0]["column"], "storage_state")

    def test_0063_requires_explicit_storage_state_without_server_default(self) -> None:
        self.assertIn('revision: str = "0063_photo_storage_outbox"', self.migration)
        storage_state_start = self.migration.index(
            'sa.Column("storage_state", sa.String(length=16), nullable=True)'
        )
        next_column = self.migration.index(
            "    op.add_column(",
            storage_state_start,
        )
        storage_state_block = self.migration[storage_state_start:next_column]
        self.assertNotIn("server_default", storage_state_block)
        self.assertIn(
            'op.alter_column("repair_photo_evidence", "storage_state", nullable=False)',
            self.migration,
        )
        self.assertIn("ck_repair_photo_storage_payload_state", self.migration)

    def test_current_application_uses_explicit_durable_storage_state(self) -> None:
        self.assertIn(
            "storage_state: Mapped[str] = mapped_column(String(16), nullable=False)",
            self.model,
        )
        self.assertIn("ck_repair_photo_storage_payload_state", self.model)

    def test_runbook_keeps_the_rollback_boundary_visible(self) -> None:
        self.assertIn("ops/cutover/phase10_rollback_v1.json", self.runbook)
        self.assertIn(
            "code-only rollback to the currently deployed Production application is not safe",
            self.runbook,
        )


if __name__ == "__main__":
    unittest.main()
