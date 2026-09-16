import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from partgraph.knowledge.reference_parts import (
    ReferencePartsAdapter,
    ReferencePartsError,
    load_reference_parts_records,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = REPO_ROOT / "api/data/reference"


class ReferencePartsDatasetTests(unittest.TestCase):
    def _write_dataset(
        self,
        root: Path,
        *,
        count: int = 2,
        unknown_source: bool = False,
    ) -> None:
        vehicle_id = str(uuid4())
        manifest = {
            "schema_version": 1,
            "dataset_key": "fixture-reviewed-oem-parts-v1",
            "vehicle": {
                "vehicle_configuration_id": vehicle_id,
                "market": "US",
                "year": 2024,
                "make": "Fixture Motors",
                "model": "MODEL X",
            },
            "review": {
                "status": "approved_for_mvp_reference",
                "reviewed_on": "2026-09-14",
                "reviewed_by": "fixture_reviewer",
                "note": "Synthetic reviewed fixture for the reference-parts adapter.",
            },
            "publication": {
                "part_manufacturer": "Fixture Motors",
                "claim_risk": "safety_critical",
                "note": "Conservative fixture risk classification.",
            },
            "sources": [
                {
                    "key": "fixture_source_a",
                    "source_class": "oem_parts",
                    "url": "https://example.invalid/catalog/a",
                },
                {
                    "key": "fixture_source_b",
                    "source_class": "oem_parts",
                    "url": "https://example.invalid/catalog/b",
                },
            ],
            "exclusions": [
                {
                    "oem_part_numbers": ["EXCLUDED-1"],
                    "reason": "Synthetic non-applicable fixture observation.",
                }
            ],
            "notes": ["Synthetic manifest note."],
            "component_files": {
                "cooling": {"path": "cooling.json", "count": count}
            },
        }
        rows = [
            {
                "system": "cooling",
                "subsystem": "radiator_and_fans",
                "name": "Radiator assembly",
                "oem_part_number": "RAD-100",
                "source_ref": "fixture_source_a",
                "fitment_status": "verified",
                "parent_assembly_part_number": "PARENT-1",
                "supersedes": ["RAD-OLD"],
                "capability_note": (
                    "Synthetic note retained outside the fitment claim."
                ),
            },
            {
                "system": "cooling",
                "subsystem": "radiator_and_fans",
                "name": "Cooling fan",
                "oem_part_number": "FAN-200",
                "source_ref": (
                    "missing_source" if unknown_source else "fixture_source_b"
                ),
                "fitment_status": "verified",
            },
        ]
        (root / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        (root / "cooling.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "dataset_key": manifest["dataset_key"],
                    "system": "cooling",
                    "components": rows,
                }
            ),
            encoding="utf-8",
        )

    def test_reviewed_dataset_becomes_source_scoped_raw_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_dataset(root)
            moment = datetime(2026, 9, 14, tzinfo=UTC)
            records = load_reference_parts_records(root, fetched_at=moment)

        self.assertEqual(len(records), 2)
        self.assertEqual(
            {record.source_ref for record in records},
            {"fixture_source_a", "fixture_source_b"},
        )
        first = next(
            record for record in records if record.source_ref == "fixture_source_a"
        )
        self.assertEqual(first.source_class, "oem_parts")
        self.assertEqual(first.record.fetched_at, moment)
        self.assertEqual(
            first.record.raw_payload["claim_risk"], "safety_critical"
        )
        self.assertEqual(len(first.record.raw_payload["rows"]), 1)
        raw_row = first.record.raw_payload["rows"][0]
        self.assertEqual(raw_row["parent_assembly_part_number"], "PARENT-1")
        self.assertEqual(raw_row["supersedes"], ["RAD-OLD"])
        self.assertEqual(
            first.record.provenance["manifest_exclusions"][0]["oem_part_numbers"],
            ["EXCLUDED-1"],
        )
        self.assertIn(
            "part_supersession",
            first.record.provenance["deferred_fact_types"],
        )

    def test_adapter_emits_only_exact_part_fitment_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_dataset(root)
            record = load_reference_parts_records(root)[0].record
            candidates = ReferencePartsAdapter().extract(record)

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        claim = candidate.candidate_payload["mechanical_claim"]
        self.assertEqual(claim["claim_domain"], "part_fitment")
        self.assertEqual(claim["claim_risk"], "safety_critical")
        self.assertTrue(claim["explicit_claim"])
        self.assertTrue(claim["exact_applicability"])
        self.assertEqual(
            candidate.vehicle_configuration_id,
            UUID(claim["vehicle_configuration_id"]),
        )
        payload = claim["claim_payload"]
        self.assertEqual(payload["part"]["manufacturer"], "Fixture Motors")
        self.assertEqual(payload["part"]["part_number"], "RAD-100")
        self.assertEqual(
            payload["component"]["display_name"], "Radiator assembly"
        )
        self.assertNotIn("parent_assembly_part_number", payload)
        self.assertNotIn("supersedes", payload)
        self.assertNotIn("capability_note", payload)

    def test_unknown_source_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_dataset(root, unknown_source=True)
            with self.assertRaisesRegex(ReferencePartsError, "undeclared source"):
                load_reference_parts_records(root)

    def test_declared_component_count_must_match_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_dataset(root, count=3)
            with self.assertRaisesRegex(ReferencePartsError, "count mismatch"):
                load_reference_parts_records(root)

    def test_repository_reviewed_parts_datasets_validate_without_vehicle_code(self) -> None:
        checked = 0
        moment = datetime(2026, 9, 14, tzinfo=UTC)
        for manifest_path in sorted(REFERENCE_ROOT.glob("*/manifest.json")):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if "publication" not in manifest:
                continue
            records = load_reference_parts_records(
                manifest_path.parent,
                fetched_at=moment,
            )
            emitted_rows = sum(
                len(record.record.raw_payload["rows"]) for record in records
            )
            declared_rows = sum(
                file_spec["count"]
                for file_spec in manifest["component_files"].values()
            )
            self.assertEqual(emitted_rows, declared_rows)
            checked += 1
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()
