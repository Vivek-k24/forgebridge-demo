import json
import unittest

from reference_fixture_support import (
    load_json,
    primary_candidate,
    primary_parts_manifest,
    primary_repair,
    primary_vehicle_id,
    primary_vehicle_snapshot,
)

REFERENCE_VEHICLE_ID = str(primary_vehicle_id())
REFERENCE_VEHICLE = primary_vehicle_snapshot()


class ReferenceRepairCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _, cls.candidate = primary_candidate()

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

    def test_candidate_is_exactly_scoped_to_primary_reference_vehicle(self) -> None:
        self.assertEqual(
            self.candidate["vehicle_configuration_id"],
            REFERENCE_VEHICLE_ID,
        )
        vehicle = self.candidate["vehicle"]
        self.assertEqual(
            vehicle,
            {key: REFERENCE_VEHICLE.get(key) for key in vehicle},
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
        manifest_path, manifest = primary_parts_manifest()
        approved_numbers: set[str] = set()
        for component in manifest["component_files"].values():
            payload = load_json(manifest_path.parent / str(component["path"]))
            rows = payload if isinstance(payload, list) else payload.get("components", [])
            for row in rows:
                part_number = row.get("oem_part_number")
                if part_number:
                    approved_numbers.add(str(part_number).casefold())

        requirements = [
            item
            for item in self.candidate["source_repair"]["requirements"]
            if item["category"] in {"part", "hardware"}
        ]
        self.assertGreaterEqual(len(requirements), 2)
        for requirement in requirements:
            requirement_key = str(requirement["requirement_key"]).casefold()
            self.assertTrue(
                any(number in requirement_key for number in approved_numbers),
                requirement_key,
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
            "diagnostic system",
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
        _, source = primary_repair("engine-water-pump-replacement")
        _, target = primary_repair("cooling-system-refill-air-bleed")
        self.assertEqual(source["vehicle_configuration_id"], REFERENCE_VEHICLE_ID)
        self.assertEqual(target["vehicle_configuration_id"], REFERENCE_VEHICLE_ID)
        self.assertEqual(source["repair_key"], "engine-water-pump-replacement")
        self.assertEqual(target["repair_key"], "cooling-system-refill-air-bleed")
        self.assertEqual(source["source_key"], target["source_key"])


if __name__ == "__main__":
    unittest.main()
