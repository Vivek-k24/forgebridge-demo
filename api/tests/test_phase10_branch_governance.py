import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "ops/cutover/phase10_branch_governance_v1.json"
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/mvp-validation.yml"
RUNBOOK_PATH = REPO_ROOT / "docs/GITHUB_BRANCH_PROTECTION_RUNBOOK.md"

EXPECTED_PHASE9_JOB_IDS = {
    "unit-domain",
    "api-contracts",
    "auth-security",
    "owner-isolation",
    "migrations",
    "production-copy-migration",
    "full-stack",
    "verified-guidance",
    "browser-e2e",
    "randomized-acceptance",
    "reference-fleet-acceptance",
    "offline-degraded",
    "timeout-ambiguous-write",
    "downstream-operation-semantics",
    "unsupported-computer-boundary",
    "durable-photo-persistence",
    "data-free-source-code",
    "rbac-authorization",
}


class Phase10BranchGovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    def test_policy_is_active_with_owner_and_api_evidence(self) -> None:
        self.assertEqual(
            self.contract["status"],
            "active_owner_applied_api_verified",
        )
        self.assertTrue(self.contract["current_state"]["main_protected"])
        self.assertEqual(self.contract["current_state"]["repository_rulesets"], 0)
        self.assertFalse(
            self.contract["current_state"][
                "administration_permission_available_to_connected_github_app"
            ]
        )
        evidence = self.contract["activation_evidence"]
        self.assertTrue(evidence["owner_reported_prepared_policy_applied"])
        self.assertTrue(evidence["github_branch_api_main_protected"])
        self.assertEqual(evidence["github_rulesets_observed"], 0)
        self.assertEqual(evidence["inferred_surface"], "classic_branch_protection")
        self.assertFalse(evidence["destructive_verification_attempted"])

    def test_solo_owner_policy_does_not_require_impossible_self_review(self) -> None:
        policy = self.contract["target_policy"]
        self.assertTrue(policy["require_pull_request_before_merging"])
        self.assertEqual(policy["required_approving_review_count"], 0)
        self.assertTrue(policy["require_conversation_resolution"])
        self.assertTrue(policy["enforce_for_administrators"])

    def test_one_stable_required_check_is_defined(self) -> None:
        policy = self.contract["target_policy"]
        self.assertEqual(policy["protected_branch"], "main")
        self.assertEqual(policy["required_status_checks"], ["MVP merge gate"])
        self.assertTrue(policy["require_branch_up_to_date_before_merging"])
        self.assertFalse(policy["require_linear_history"])

    def test_final_validation_runs_for_every_pull_request(self) -> None:
        self.assertIn("on:\n  pull_request:\n  push:", self.workflow)
        pull_request_section = self.workflow.split("  pull_request:", 1)[1].split(
            "  push:", 1
        )[0]
        self.assertNotIn("paths:", pull_request_section)

    def test_pr_head_does_not_create_duplicate_push_merge_gate(self) -> None:
        push_section = self.workflow.split("  push:", 1)[1].split(
            "  workflow_dispatch:", 1
        )[0]
        self.assertIn("- main", push_section)
        self.assertNotIn("partgraph-mvp-consolidation", push_section)

    def test_merge_gate_depends_on_every_phase9_job(self) -> None:
        job_match = re.search(
            r"^  mvp-merge-gate:\n(?P<body>.*)\Z",
            self.workflow,
            flags=re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(job_match)
        assert job_match is not None
        body = job_match.group("body")
        self.assertIn("name: MVP merge gate", body)
        for job_id in EXPECTED_PHASE9_JOB_IDS:
            self.assertIn(f"      - {job_id}\n", body)
        self.assertIn("if: always()", body)
        self.assertIn("NEEDS_JSON:", body)
        self.assertIn('if result.get("result") != "success"', body)

    def test_destructive_branch_operations_are_blocked_by_target_policy(self) -> None:
        policy = self.contract["target_policy"]
        self.assertTrue(policy["block_force_pushes"])
        self.assertTrue(policy["block_deletions"])
        self.assertFalse(policy["lock_branch"])

    def test_runbook_preserves_feature_branch_workflow(self) -> None:
        self.assertIn("Protect **`main` only**", self.runbook)
        self.assertIn("Do not protect `partgraph-mvp-consolidation`", self.runbook)


if __name__ == "__main__":
    unittest.main()
