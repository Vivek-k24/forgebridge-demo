import json
import unittest
from pathlib import Path

CANDIDATE_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "reference_candidates"
    / "2009_honda_civic_hybrid_water_pump_v1"
    / "candidate.json"
)
REFERENCE_DIR = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "reference"
    / "2009_honda_civic_hybrid_repairs_v1"
)
REFERENCE_VEHICLE_ID = "7feb13e9-bca0-5d8b-b701-f0260cce5da1"


class ReferenceRepairCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))

    def test_project_owner_approval_keeps_automation_disabled(self) -> None:
        self.assertEqual(
            self.candidate["review_status"],
            "approved_for_mvp_reference",
        )
        source_review = self.candidate["source_review"]
        self.assertEqual(source_review["license_status"], "approved")
        self.assertEqual(source_review["reviewed_on"], "2026-09-15")
        self.assertEqual(source_review["reviewed_by"], "project_owner")
        self.assertFalse(source_review["automation_allowed"])
        self.assertTrue(
            self.candidate["publication_boundary"]["canonical_publication_allowed"]
        )

    def test_candidate_is_exactly_scoped_to_reference_civic_hybrid(self) -> None:
        self.assertEqual(
            self.candidate["vehicle_configuration_id"],
            REFERENCE_VEHICLE_ID,
        )
        vehicle = self.candidate["vehicle"]
        self.assertEqual(
            (vehicle["year"], vehicle["make"], vehicle["model"], vehicle["trim"]),
            (2009, "Honda", "CIVIC", "HYBRID"),
        )

    def test_water_pump_replacement_creates_supported_refill_bleed_candidate(self) -> None:
        source = self.candidate["source_repair"]
        target = self.candidate["target_repair"]
        relation = self.candidate["downstream_relation"]

        self.assertEqual(source["repair_key"], "engine-water-pump-replacement")
        self.assertEqual(target["repair_key"], "cooling-system-refill-air-bleed")
        self.assertEqual(relation["trigger_type"], "action_completed")
        self.assertEqual(relation["trigger_action_key"], "install-water-pump")
        self.assertEqual(relation["milestone_type"], "physical_replacement")
        self.assertEqual(relation["support_state"], "supported")
        self.assertEqual(relation["target_repair_key"], target["repair_key"])

        pump_action = next(
            item
            for item in source["actions"]
            if item["action_key"] == relation["trigger_action_key"]
        )
        self.assertEqual(pump_action["milestone_type"], "physical_replacement")
        self.assertEqual(
            pump_action["downstream_requirement_key"],
            relation["requirement_key"],
        )
        self.assertEqual(
            pump_action["downstream_target_repair_key"],
            relation["target_repair_key"],
        )

    def test_existing_reviewed_part_numbers_are_used_without_inference(self) -> None:
        requirements = {
            item["use_key"]: item
            for item in self.candidate["source_repair"]["requirements"]
        }
        self.assertEqual(
            requirements["replacement-water-pump"]["requirement_key"],
            "part.honda.19200-rmx-003",
        )
        self.assertEqual(
            requirements["new-water-pump-seal"]["requirement_key"],
            "hardware.honda.19222-pza-003",
        )

    def test_physical_bleed_actions_do_not_smuggle_in_computer_service(self) -> None:
        target = self.candidate["target_repair"]
        executable_content = {
            "requirements": target["requirements"],
            "operations": target["operations"],
            "actions": target["actions"],
        }
        serialized = json.dumps(executable_content).lower()
        for forbidden in (
            "honda diagnostic system",
            "hds communicates",
            "service reminder reset",
            "programming",
            "coding",
            "calibration",
            "initialization",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, serialized)

    def test_approved_candidate_has_canonical_reference_files(self) -> None:
        source = json.loads(
            (REFERENCE_DIR / "engine_water_pump_replacement.json").read_text(
                encoding="utf-8"
            )
        )
        target = json.loads(
            (REFERENCE_DIR / "cooling_system_refill_air_bleed.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(source["vehicle_configuration_id"], REFERENCE_VEHICLE_ID)
        self.assertEqual(target["vehicle_configuration_id"], REFERENCE_VEHICLE_ID)
        self.assertEqual(source["repair_key"], "engine-water-pump-replacement")
        self.assertEqual(target["repair_key"], "cooling-system-refill-air-bleed")
        self.assertEqual(source["source_key"], target["source_key"])


if __name__ == "__main__":
    unittest.main()
