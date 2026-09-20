import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DECISIONS_PATH = REPO_ROOT / "ops/cutover/phase10_owner_decisions_v1.json"
AUDIT_PATH = REPO_ROOT / "docs/AUDIT_STATUS.md"
PREFLIGHT_PATH = REPO_ROOT / "ops/cutover/phase10_preflight_v1.json"
RUNBOOK_PATH = REPO_ROOT / "docs/OWNER_LAUNCH_DECISIONS.md"


class Phase10OwnerDecisionPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.packet = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))
        cls.audit = AUDIT_PATH.read_text(encoding="utf-8")
        cls.preflight = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
        cls.runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    def test_packet_contains_every_blocked_audit_finding(self) -> None:
        blocked = set(
            re.findall(
                r"^\| (PG-AUD-[A-Z0-9-]+) \| BLOCKED \|",
                self.audit,
                flags=re.MULTILINE,
            )
        )
        packet_ids = {item["id"] for item in self.packet["launch_blockers"]}
        self.assertEqual(blocked, packet_ids)

    def test_packet_does_not_authorize_production(self) -> None:
        self.assertEqual(self.packet["status"], "owner_decisions_pending")
        self.assertFalse(self.packet["production_mutation_authorized"])
        self.assertFalse(self.preflight["production_mutation_authorized"])
        self.assertEqual(self.preflight["status"], "no_go")

    def test_nhtsa_proof_is_separate_from_owner_blockers(self) -> None:
        proof_ids = {
            item["id"] for item in self.packet["remaining_non_owner_execution"]
        }
        self.assertEqual(proof_ids, {"PG-AUD-ROAD-002"})
        self.assertFalse(
            self.packet["remaining_non_owner_execution"][0]["mvp_launch_requirement"]
        )

    def test_post_mvp_work_is_not_promoted_into_launch_scope(self) -> None:
        joined = "\n".join(self.packet["post_mvp_scope"])
        self.assertIn("PG-AUD-ROAD-003", joined)
        self.assertIn("PG-AUD-UI-008", joined)
        self.assertIn("CURRENT CONTROL COMPLETE", joined)

    def test_runbook_keeps_exact_candidate_authorization_rule(self) -> None:
        self.assertIn("Only authorize after a fresh Phase 10 preflight reports **GO**", self.runbook)
        self.assertIn("exact candidate commit", self.runbook)
        self.assertIn("There are **no decision-free remediation fixes left**", self.runbook)


if __name__ == "__main__":
    unittest.main()
