import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "ops/cutover/phase10_preflight_v1.json"
ROLLBACK_PATH = REPO_ROOT / "ops/cutover/phase10_rollback_v1.json"
AUDIT_PATH = REPO_ROOT / "docs/AUDIT_STATUS.md"
PREFLIGHT_DOC_PATH = REPO_ROOT / "docs/PRODUCTION_CUTOVER_PREFLIGHT.md"
MIGRATION_RUNBOOK_PATH = REPO_ROOT / "docs/DATABASE_MIGRATION_PROMOTION_RUNBOOK.md"


class Phase10PreflightContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        cls.rollback = json.loads(ROLLBACK_PATH.read_text(encoding="utf-8"))
        cls.audit = AUDIT_PATH.read_text(encoding="utf-8")
        cls.preflight_doc = PREFLIGHT_DOC_PATH.read_text(encoding="utf-8")
        cls.migration_runbook = MIGRATION_RUNBOOK_PATH.read_text(encoding="utf-8")

    def test_current_contract_fails_closed(self) -> None:
        self.assertEqual(self.contract["status"], "no_go")
        self.assertTrue(self.contract["must_refresh_before_cutover"])
        self.assertFalse(self.contract["production_mutation_authorized"])
        self.assertIn("GO is permitted only", self.contract["go_rule"])

    def test_every_current_blocked_audit_finding_is_surfaced(self) -> None:
        blocked = set(
            re.findall(
                r"^\| (PG-AUD-[A-Z0-9-]+) \| BLOCKED \|",
                self.audit,
                flags=re.MULTILINE,
            )
        )
        hard = {
            item["finding_id"]
            for item in self.contract["hard_cutover_gates"]
        }
        decisions = {
            item["finding_id"]
            for item in self.contract["decision_required_findings"]
        }
        self.assertEqual(
            blocked,
            hard | decisions,
            "Every active BLOCKED audit finding must be visible in preflight.",
        )

    def test_known_hard_cutover_gates_remain_blocked(self) -> None:
        gates = {
            item["finding_id"]: item["state"]
            for item in self.contract["hard_cutover_gates"]
        }
        self.assertEqual(gates["PG-AUD-REL-001"], "blocked")
        self.assertEqual(gates["PG-AUD-DEP-005"], "blocked")
        self.assertEqual(gates["PG-AUD-DEP-001"], "blocked")

    def test_preflight_preserves_coordinated_rollback_rule(self) -> None:
        self.assertFalse(
            self.contract["rollback_contract"]["code_only_rollback_after_0063_safe"]
        )
        self.assertFalse(
            self.rollback["code_only_rollback_safe_after_schema_promotion"]
        )
        self.assertEqual(
            self.contract["rollback_contract"]["path"],
            "ops/cutover/phase10_rollback_v1.json",
        )

    def test_production_baseline_and_backup_gap_are_explicit(self) -> None:
        production = self.contract["observed_snapshot"]["production"]
        self.assertEqual(production["database_revision"], "0020_catalog_coverage")
        self.assertEqual(
            production["neon_branch_id"],
            "br-shiny-silence-aexgk2zm",
        )
        self.assertEqual(production["automatic_snapshot_schedule_entries"], 0)
        self.assertEqual(production["history_retention_seconds"], 21600)
        self.assertFalse(production["neon_branch_protected"])

    def test_deployment_order_risk_is_tied_to_observed_production_behavior(self) -> None:
        observed = self.contract["observed_snapshot"][
            "deployment_governance_observation"
        ]
        self.assertEqual(
            observed["production_commit"],
            "d68606162c725348779e2d4f93e8819eb8469f21",
        )
        self.assertEqual(observed["commit_files_changed"], ["docs/ROADMAP_LIVE.md"])
        self.assertIn("Production deployment", observed["meaning"])

    def test_preview_protection_is_not_misreported_as_readiness_failure(self) -> None:
        preview = self.contract["observed_snapshot"]["preview"]
        self.assertEqual(preview["deployment_state"], "READY")
        self.assertEqual(preview["last_confirmed_application_readiness_http_status"], 200)
        self.assertEqual(preview["current_unauthenticated_probe_http_status"], 302)
        self.assertIn("SSO protection", preview["current_probe_interpretation"])

    def test_runbooks_do_not_require_impossible_premerge_dispatch(self) -> None:
        stale = (
            "still requires its own first successful manual dispatch"
        )
        self.assertNotIn(stale, self.migration_runbook)
        self.assertIn("default branch", self.migration_runbook)
        self.assertIn("not a prerequisite", self.migration_runbook)

    def test_operator_document_keeps_preflight_read_only_until_approval(self) -> None:
        self.assertIn("Current assessment — NO-GO", self.preflight_doc)
        self.assertIn(
            "All steps before the explicit approval point are read-only",
            self.preflight_doc,
        )
        self.assertIn("Do not merge PR #84 merely to discover", self.preflight_doc)


if __name__ == "__main__":
    unittest.main()
