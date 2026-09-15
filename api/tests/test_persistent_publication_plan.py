import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = REPO_ROOT / "api/data/reference/persistent_publication_plan_v1.json"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class PersistentPublicationPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = _load_json(PLAN_PATH)
        datasets = cls.plan["datasets"]
        cls.parts_manifest = _load_json(REPO_ROOT / datasets["parts_manifest"])
        cls.repair_manifest = _load_json(REPO_ROOT / datasets["repair_manifest"])
        cls.coverage = _load_json(REPO_ROOT / datasets["primary_vehicle_coverage"])

    def test_publication_is_explicit_and_not_deployment_driven(self) -> None:
        policy = self.plan["policy"]
        self.assertFalse(policy["deployment_is_publication"])
        self.assertEqual(policy["publication_trigger"], "operator_only")
        self.assertTrue(policy["explicit_environment_authorization_required"])
        self.assertFalse(policy["production_publication_authorized"])
        self.assertTrue(policy["source_automation_rights_unchanged"])
        self.assertFalse(policy["direct_canonical_sql_allowed"])
        self.assertEqual(
            policy["publication_path"],
            "immutable_evidence_then_verified_claim_then_restricted_materializer",
        )

    def test_vehicle_scope_matches_all_reviewed_reference_datasets(self) -> None:
        vehicle_id = self.plan["vehicle_configuration_id"]
        self.assertEqual(
            self.parts_manifest["vehicle"]["vehicle_configuration_id"], vehicle_id
        )
        self.assertEqual(self.repair_manifest["vehicle_configuration_id"], vehicle_id)
        self.assertEqual(self.coverage["vehicle_configuration_id"], vehicle_id)

    def test_plan_counts_are_derived_from_versioned_datasets(self) -> None:
        bundle = self.plan["reference_bundle"]

        fitment_count = sum(
            int(item["count"])
            for item in self.parts_manifest["component_files"].values()
        )
        self.assertEqual(bundle["part_fitment_claims"], fitment_count)

        manifest_repairs = {
            repair["repair_key"]: repair for repair in self.repair_manifest["repairs"]
        }
        planned_repairs = {repair["repair_key"]: repair for repair in bundle["repairs"]}
        self.assertEqual(set(planned_repairs), set(manifest_repairs))

        requirement_total = 0
        procedure_total = 0
        for repair_key, manifest_entry in manifest_repairs.items():
            repair_path = (
                REPO_ROOT
                / "api/data/reference/2009_honda_civic_hybrid_repairs_v1"
                / manifest_entry["path"]
            )
            repair_data = _load_json(repair_path)
            requirement_count = len(repair_data["requirements"])
            procedure_count = len(repair_data["actions"])

            self.assertEqual(manifest_entry["requirement_count"], requirement_count)
            self.assertEqual(manifest_entry["action_count"], procedure_count)
            self.assertEqual(
                planned_repairs[repair_key]["requirement_claims"], requirement_count
            )
            self.assertEqual(
                planned_repairs[repair_key]["procedure_claims"], procedure_count
            )
            requirement_total += requirement_count
            procedure_total += procedure_count

        structure_count = len(self.coverage["structure"])
        specification_count = len(self.coverage["specifications"])
        self.assertEqual(bundle["vehicle_structure_claims"], structure_count)
        self.assertEqual(bundle["vehicle_specification_claims"], specification_count)

        expected_claim_total = (
            int(bundle["vehicle_identity_claims"])
            + fitment_count
            + requirement_total
            + procedure_total
            + structure_count
            + specification_count
        )
        target = bundle["expected_scoped_target"]
        self.assertEqual(target["verified_evidence"], expected_claim_total)
        self.assertEqual(target["mechanical_claims"], expected_claim_total)
        self.assertEqual(target["part_fitments"], fitment_count)
        self.assertEqual(target["repair_definitions"], len(manifest_repairs))
        self.assertEqual(target["vehicle_structure_nodes"], structure_count)
        self.assertEqual(target["vehicle_specification_values"], specification_count)

    def test_recorded_preview_delta_is_arithmetically_consistent(self) -> None:
        snapshot = self.plan["observed_preview_snapshot"]
        target = self.plan["reference_bundle"]["expected_scoped_target"]
        increment = self.plan["expected_increment_from_observed_preview"]

        self.assertEqual(
            increment["verified_evidence"],
            target["verified_evidence"] - snapshot["verified_evidence"],
        )
        self.assertEqual(
            increment["mechanical_claims"],
            target["mechanical_claims"] - snapshot["mechanical_claims"],
        )
        self.assertEqual(
            increment["repair_definitions"],
            target["repair_definitions"] - len(snapshot["repair_definitions"]),
        )
        self.assertEqual(
            increment["vehicle_structure_nodes"],
            target["vehicle_structure_nodes"] - snapshot["vehicle_structure_nodes"],
        )
        self.assertEqual(
            increment["vehicle_specification_values"],
            target["vehicle_specification_values"]
            - snapshot["vehicle_specification_values"],
        )

        persistent_repairs = set(snapshot["repair_definitions"])
        repair_counts = {
            repair["repair_key"]: (
                repair["requirement_claims"] + repair["procedure_claims"]
            )
            for repair in self.plan["reference_bundle"]["repairs"]
        }
        expected_snapshot_claims = (
            self.plan["reference_bundle"]["vehicle_identity_claims"]
            + self.plan["reference_bundle"]["part_fitment_claims"]
            + sum(repair_counts[key] for key in persistent_repairs)
        )
        self.assertEqual(snapshot["mechanical_claims"], expected_snapshot_claims)
        self.assertEqual(snapshot["verified_evidence"], expected_snapshot_claims)

    def test_generic_publisher_is_explicitly_deferred_without_special_casing(self) -> None:
        deferred = self.plan["deferred"]
        self.assertEqual(
            deferred["generic_reusable_persistent_bundle_publisher"],
            "Phase 6 broad repair-knowledge population",
        )
        self.assertIn("generic operator", deferred["reason"])
        self.assertNotIn("hardcode", deferred["reason"].lower())


if __name__ == "__main__":
    unittest.main()
