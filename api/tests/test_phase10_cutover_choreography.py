import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHOREOGRAPHY_PATH = REPO_ROOT / "ops/cutover/phase10_cutover_choreography_v1.json"
PREFLIGHT_PATH = REPO_ROOT / "ops/cutover/phase10_preflight_v1.json"
ROLLBACK_PATH = REPO_ROOT / "ops/cutover/phase10_rollback_v1.json"
DOC_PATH = REPO_ROOT / "docs/PRODUCTION_CUTOVER_CHOREOGRAPHY.md"
VERCEL_CONFIG_PATH = REPO_ROOT / "api/vercel.json"


class Phase10CutoverChoreographyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CHOREOGRAPHY_PATH.read_text(encoding="utf-8"))
        cls.preflight = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
        cls.rollback = json.loads(ROLLBACK_PATH.read_text(encoding="utf-8"))
        cls.doc = DOC_PATH.read_text(encoding="utf-8")
        cls.vercel_config = json.loads(VERCEL_CONFIG_PATH.read_text(encoding="utf-8"))

    def test_choreography_is_prepared_but_not_authorized(self) -> None:
        self.assertEqual(self.contract["status"], "prepared_not_authorized")
        self.assertFalse(self.contract["production_mutation_authorized"])
        self.assertEqual(self.preflight["status"], "no_go")
        self.assertFalse(self.preflight["production_mutation_authorized"])

    def test_traffic_barrier_is_selected_but_not_production_activated(self) -> None:
        barrier = self.contract["traffic_barrier"]
        self.assertEqual(barrier["selected"], "vercel_authentication_all")
        self.assertEqual(
            barrier["state"],
            "selected_pending_production_activation_and_test",
        )
        ids = {item["id"] for item in barrier["acceptable_methods"]}
        self.assertEqual(
            ids,
            {"vercel_authentication_all", "dedicated_maintenance_deployment"},
        )
        self.assertEqual(
            barrier["capability_evidence"]["availability"],
            "Vercel Authentication can protect all deployments, including Production, on every plan.",
        )
        activation = barrier["activation_contract"]
        self.assertEqual(
            activation["enable_body"]["ssoProtection"]["deploymentType"],
            "all",
        )
        self.assertFalse(activation["production_change_authorized"])
        self.assertIn(
            "restore the exact protection configuration",
            activation["restore_previous_settings"].lower(),
        )

    def test_candidate_is_staged_before_database_migration(self) -> None:
        self.assertEqual(
            self.contract["candidate_artifact"]["strategy"],
            "production_target_without_domain",
        )
        self.assertEqual(
            self.contract["candidate_artifact"]["vercel_command_contract"],
            "vercel deploy --prod --skip-domain",
        )
        steps = {item["phase"]: item for item in self.contract["ordered_steps"]}
        self.assertLess(steps["stage"]["number"], steps["freeze"]["number"])
        self.assertLess(steps["freeze"]["number"], steps["migrate"]["number"])
        self.assertLess(steps["migrate"]["number"], steps["verify_candidate"]["number"])
        self.assertLess(steps["verify_candidate"]["number"], steps["promote"]["number"])
        self.assertLess(steps["promote"]["number"], steps["open"]["number"])

    def test_public_traffic_stays_blocked_through_promotion_verification(self) -> None:
        for step in self.contract["ordered_steps"]:
            if step["phase"] in {
                "freeze",
                "backup",
                "migrate",
                "verify_database",
                "verify_candidate",
                "promote",
                "verify_live",
            }:
                self.assertEqual(
                    step["public_traffic"],
                    "blocked_or_maintenance_only",
                    step["phase"],
                )

    def test_old_application_is_never_allowed_against_0063_as_a_shortcut(self) -> None:
        shortcuts = "\n".join(self.contract["traffic_barrier"]["rejected_shortcuts"])
        self.assertIn("old application against schema 0063", shortcuts)
        self.assertFalse(
            self.rollback["code_only_rollback_safe_after_schema_promotion"]
        )

    def test_normal_git_deployment_is_not_silently_changed_yet(self) -> None:
        git_config = self.vercel_config.get("git", {})
        self.assertNotIn(
            "deploymentEnabled",
            git_config,
            "DEP-005 remains governance-blocked; do not silently change Production "
            "Git deployment behavior before explicit authorization.",
        )

    def test_document_keeps_pr_merge_out_of_the_cutover_ordering_mechanism(self) -> None:
        self.assertIn(
            "Do not use PR merge as the mechanism that chooses the Production deployment.",
            self.doc,
        )
        self.assertIn("traffic barrier", self.doc)
        self.assertIn("Vercel Authentication with scope = All Deployments", self.doc)
        self.assertIn("vercel project protection partgraph-main --format json", self.doc)
        self.assertIn("--skip-domain", self.doc)


if __name__ == "__main__":
    unittest.main()
