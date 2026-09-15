import ast
import unittest
from collections import Counter
from pathlib import Path

from partgraph.equipment.catalog_dataset import (
    equipment_catalog_dataset_version,
    load_equipment_catalog_rows,
    load_equipment_category_meta,
    load_retired_catalog_keys,
)
from partgraph.equipment.catalog_meta import CATEGORY_META as ACTIVE_CATEGORY_META
from partgraph.equipment.catalog_seed_v1 import (
    CATEGORY_LIMITS,
    CATEGORY_META,
    EXPECTED_ITEM_COUNT,
    build_equipment_catalog_seed,
)
from partgraph.equipment.inventory_catalog_v2 import (
    ENGINE_OIL_GRADES,
    LUG_NUT_THREAD_SIZES,
    RETIRED_CATALOG_KEYS,
    current_inventory_catalog,
)
from partgraph.equipment.manual_reference_v1 import (
    MANUAL_REFERENCE_QUERY_TARGETS,
    REFERENCE_ADDITIONS,
    augment_equipment_catalog_rows,
)
from partgraph.equipment.service import _search_without_whitespace

API_ROOT = Path(__file__).resolve().parents[1]
LEGACY_GENERATOR_MODULES = {
    "partgraph.equipment.catalog_seed_v1",
    "partgraph.equipment.inventory_catalog_v2",
    "partgraph.equipment.manual_reference_v1",
}


def _matches(rows: list[dict[str, str]], query: str) -> set[str]:
    normalized_query = " ".join(query.strip().split()).lower()
    compact_query = _search_without_whitespace(normalized_query)
    return {
        row["catalog_key"]
        for row in rows
        if normalized_query in f"{row['name']} {row['keywords']}".lower()
        or compact_query in _search_without_whitespace(f"{row['name']} {row['keywords']}")
    }


def _legacy_current_rows() -> list[dict[str, str]]:
    """Rebuild the historical migration catalog only for parity verification."""
    return current_inventory_catalog(
        augment_equipment_catalog_rows(build_equipment_catalog_seed())
    )


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


class EquipmentCatalogSeedTests(unittest.TestCase):
    def test_legacy_migration_equipment_seed_is_stable_and_unique(self) -> None:
        rows = build_equipment_catalog_seed()

        self.assertEqual(len(rows), EXPECTED_ITEM_COUNT)
        self.assertEqual(EXPECTED_ITEM_COUNT, 1107)
        self.assertEqual(len({row["catalog_key"] for row in rows}), EXPECTED_ITEM_COUNT)
        self.assertTrue(all(row["name"].strip() for row in rows))
        self.assertTrue(all(row["category"] in CATEGORY_META for row in rows))

        counts = Counter(row["category"] for row in rows)
        self.assertEqual(counts, Counter(CATEGORY_LIMITS))

    def test_versioned_dataset_matches_legacy_migration_catalog_exactly(self) -> None:
        legacy_rows = _legacy_current_rows()
        dataset_rows = load_equipment_catalog_rows()

        self.assertEqual(equipment_catalog_dataset_version(), "equipment-catalog-v1")
        self.assertEqual(dataset_rows, legacy_rows)
        self.assertEqual(len(dataset_rows), 1178)
        self.assertEqual(load_equipment_category_meta(), ACTIVE_CATEGORY_META)
        self.assertEqual(load_retired_catalog_keys(), frozenset(RETIRED_CATALOG_KEYS))

    def test_active_paths_do_not_import_legacy_catalog_generators(self) -> None:
        active_paths = (
            API_ROOT / "partgraph" / "equipment" / "catalog_meta.py",
            API_ROOT / "scripts" / "seed_equipment_catalog.py",
        )
        for path in active_paths:
            imported = _imported_modules(path)
            self.assertTrue(
                "partgraph.equipment.catalog_dataset" in imported
                or "catalog_dataset" in imported,
                f"active equipment path must use the versioned dataset: {path}",
            )
            self.assertFalse(
                imported & LEGACY_GENERATOR_MODULES,
                f"active equipment path imports legacy generator(s): {path}",
            )

    def test_versioned_dataset_returns_mutable_row_copies(self) -> None:
        first = load_equipment_catalog_rows()
        second = load_equipment_catalog_rows()
        first[0]["name"] = "changed only in caller"
        self.assertNotEqual(first[0]["name"], second[0]["name"])

    def test_equipment_search_ignores_spacing(self) -> None:
        self.assertEqual(_search_without_whitespace("10 mm"), "10mm")
        self.assertEqual(_search_without_whitespace("10mm"), "10mm")
        self.assertEqual(_search_without_whitespace("  3/8   in  drive "), "3/8indrive")

    def test_manual_reference_equipment_is_searchable_in_versioned_dataset(self) -> None:
        rows = load_equipment_catalog_rows()
        for query, expected_keys in MANUAL_REFERENCE_QUERY_TARGETS.items():
            self.assertTrue(
                set(expected_keys).issubset(_matches(rows, query)),
                f"manual equipment query is not fully covered: {query!r}",
            )

    def test_versioned_catalog_includes_fluids_and_wheel_hardware(self) -> None:
        rows = load_equipment_catalog_rows()
        self.assertEqual(len(rows), 1178)
        self.assertEqual(len({row["catalog_key"] for row in rows}), len(rows))
        self.assertFalse(load_retired_catalog_keys() & {row["catalog_key"] for row in rows})

        counts = Counter(row["category"] for row in rows)
        self.assertEqual(counts["engine-oil"], 42)
        self.assertEqual(counts["coolant-antifreeze"], 12)
        self.assertEqual(counts["washer-fluid"], 4)
        self.assertEqual(counts["wheel-hardware"], len(LUG_NUT_THREAD_SIZES))
        expected_categories = {
            "engine-oil",
            "coolant-antifreeze",
            "washer-fluid",
            "wheel-hardware",
        }
        self.assertTrue(expected_categories.issubset(ACTIVE_CATEGORY_META))

    def test_engine_oil_grade_and_formulation_combinations_are_searchable(self) -> None:
        rows = load_equipment_catalog_rows()
        expected_oil_count = sum(len(grades) for _, grades in ENGINE_OIL_GRADES.values())
        self.assertEqual(expected_oil_count, 42)
        self.assertIn("full-synthetic-engine-oil-sae-0w-20", _matches(rows, "full synthetic 0w20"))
        self.assertIn("full-synthetic-engine-oil-sae-0w-12", _matches(rows, "0w12"))
        self.assertIn(
            "high-mileage-synthetic-blend-engine-oil-sae-20w-50",
            _matches(rows, "high mileage 20w50"),
        )
        self.assertIn(
            "high-mileage-conventional-engine-oil-sae-10w-40",
            _matches(rows, "conventional high mileage 10w40"),
        )

    def test_coolant_funnel_lug_nuts_and_refrigerant_specific_ac_equipment_are_covered(self) -> None:
        rows = load_equipment_catalog_rows()
        self.assertIn("spill-free-coolant-funnel", _matches(rows, "coolant air bleed funnel"))
        self.assertIn("wheel-lug-nut-m12-x-1-5", _matches(rows, "M12x1.5 lug nut"))
        self.assertIn(
            "r-134a-a-c-refrigerant-recover-recycle-recharge-machine",
            _matches(rows, "R134a recovery recharge machine"),
        )
        self.assertIn(
            "r-1234yf-a-c-refrigerant-recover-recycle-recharge-machine",
            _matches(rows, "R1234yf recovery recharge machine"),
        )
        self.assertIn(
            "r-134a-r-1234yf-dual-refrigerant-a-c-service-machine",
            _matches(rows, "R134a R1234yf dual refrigerant machine"),
        )
        self.assertIn(
            "r-744-co2-a-c-recharge-service-station",
            _matches(rows, "R744 CO2 recharge station"),
        )


if __name__ == "__main__":
    unittest.main()
