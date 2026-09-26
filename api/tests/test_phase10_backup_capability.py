import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPABILITY_PATH = REPO_ROOT / "ops/cutover/phase10_backup_capability_v1.json"
PREFLIGHT_PATH = REPO_ROOT / "ops/cutover/phase10_preflight_v1.json"
AUDIT_PATH = REPO_ROOT / "docs/AUDIT_STATUS.md"
DR_PATH = REPO_ROOT / "docs/DISASTER_RECOVERY_RUNBOOK.md"


class Phase10BackupCapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capability = json.loads(CAPABILITY_PATH.read_text(encoding="utf-8"))
        cls.preflight = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
        cls.audit = AUDIT_PATH.read_text(encoding="utf-8")
        cls.dr = DR_PATH.read_text(encoding="utf-8")

    def test_current_project_cannot_close_backup_gate_automatically(self) -> None:
        self.assertEqual(
            self.capability["status"],
            "blocked_by_current_neon_project_capability",
        )
        self.assertFalse(self.capability["production_mutation_authorized"])
        self.assertEqual(self.capability["project"]["subscription_type"], "free_v3")
        self.assertEqual(self.capability["project"]["history_retention_seconds"], 21600)

    def test_non_production_probes_record_provider_rejections(self) -> None:
        probes = {
            item["capability"]: item
            for item in self.capability["non_production_capability_probes"]
        }
        self.assertEqual(probes["automatic_snapshot_schedule"]["result"], "rejected")
        self.assertIn(
            "not enabled for this project",
            probes["automatic_snapshot_schedule"]["provider_message"],
        )
        self.assertEqual(probes["branch_protection"]["result"], "rejected")
        self.assertEqual(
            probes["branch_protection"]["account_protected_branches_observed"],
            0,
        )
        self.assertIn(
            "current plan",
            probes["branch_protection"]["provider_message"],
        )

    def test_restore_mechanics_are_not_misrepresented_as_backup_freshness(self) -> None:
        proven = self.capability["proven_capabilities"]
        self.assertTrue(proven["manual_snapshot_creation"])
        self.assertTrue(proven["isolated_snapshot_restore"])
        self.assertTrue(proven["representative_owner_state_restore_verified"])
        self.assertIn("backup freshness", self.dr.lower())
        self.assertIn("remains blocked", self.dr.lower())

    def test_preflight_keeps_rel_001_blocked(self) -> None:
        gates = {
            item["finding_id"]: item["state"]
            for item in self.preflight["hard_cutover_gates"]
        }
        self.assertEqual(gates["PG-AUD-REL-001"], "blocked")
        self.assertIn("PG-AUD-REL-001 | BLOCKED", self.audit)


if __name__ == "__main__":
    unittest.main()
