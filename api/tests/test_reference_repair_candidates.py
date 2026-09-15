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
REFERENCE_VEHICLE_ID = "7feb13e9-bca0-5d8b-b701-f0260cce5da1"


class ReferenceRepairCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))

    def test_candidate_stays_outside_canonical_truth_until_review(self) -> None:
        self.assertEqual(
            self.candidate["review_status"],
            "pending_project_owner_review",
        )
        source_review = self.candidate["source_review"]
        self.assertEqual(source_review["license_status"], "unreviewed")
        self.assertFalse(source_review["automation_allowed"])
        self.assertFalse(
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

    def test_existing_reviewed_part_numbers_are_used_without_inference(self) -> None:
        requirements = {
            item["use_key"]: item for item in self.candidate["source_repair"]["requirements"]
        }
        self.assertEqual(
            requirements["replacement-water-pump"]["requirement_key"],
            "part.honda.19200-rmx-003",
        )
        self.assertEqual(
            requirements["new-water-pump-seal"]["requirement_key"],
            "hardware.honda.19222-pza-003",
        )

    def test_physical_bleed_candidate_does_not_smuggle_in_computer_service(self) -> None:
        serialized = json.dumps(self.candidate["target_repair"]).lower()
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


if __name__ == "__main__":
    unittest.main()
