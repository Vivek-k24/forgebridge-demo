import unittest
from collections import Counter

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


def _matches(rows: list[dict[str, str]], query: str) -> set[str]:
    normalized_query = " ".join(query.strip().split()).lower()
    compact_query = _search_without_whitespace(normalized_query)
    return {
        row["catalog_key"]
        for row in rows
        if normalized_query in f"{row['name']} {row['keywords']}".lower()
        or compact_query in _search_without_whitespace(f"{row['name']} {row['keywords']}")
    }


class EquipmentCatalogSeedTests(unittest.TestCase):
    def test_equipment_catalog_seed_is_stable_and_unique(self) -> None:
        rows = build_equipment_catalog_seed()

        self.assertEqual(len(rows), EXPECTED_ITEM_COUNT)
        self.assertEqual(EXPECTED_ITEM_COUNT, 1107)
        self.assertEqual(len({row["catalog_key"] for row in rows}), EXPECTED_ITEM_COUNT)
        self.assertTrue(all(row["name"].strip() for row in rows))
        self.assertTrue(all(row["category"] in CATEGORY_META for row in rows))

        counts = Counter(row["category"] for row in rows)
        self.assertEqual(counts, Counter(CATEGORY_LIMITS))

    def test_equipment_search_ignores_spacing(self) -> None:
        self.assertEqual(_search_without_whitespace("10 mm"), "10mm")
        self.assertEqual(_search_without_whitespace("10mm"), "10mm")
        self.assertEqual(_search_without_whitespace("  3/8   in  drive "), "3/8indrive")

    def test_manual_reference_equipment_is_searchable(self) -> None:
        rows = augment_equipment_catalog_rows(build_equipment_catalog_seed())
        self.assertEqual(len(rows), EXPECTED_ITEM_COUNT + len(REFERENCE_ADDITIONS))
        self.assertEqual(len({row["catalog_key"] for row in rows}), len(rows))

        for query, expected_keys in MANUAL_REFERENCE_QUERY_TARGETS.items():
            self.assertTrue(
                set(expected_keys).issubset(_matches(rows, query)),
                f"manual equipment query is not fully covered: {query!r}",
            )

    def test_current_inventory_catalog_includes_fluids_and_wheel_hardware(self) -> None:
        rows = current_inventory_catalog(
            augment_equipment_catalog_rows(build_equipment_catalog_seed())
        )
        self.assertEqual(len(rows), 1174)
        self.assertEqual(len({row["catalog_key"] for row in rows}), len(rows))
        self.assertFalse(RETIRED_CATALOG_KEYS & {row["catalog_key"] for row in rows})

        counts = Counter(row["category"] for row in rows)
        self.assertEqual(counts["engine-oil"], 42)
        self.assertEqual(counts["coolant-antifreeze"], 10)
        self.assertEqual(counts["washer-fluid"], 4)
        self.assertEqual(counts["wheel-hardware"], len(LUG_NUT_THREAD_SIZES))
        self.assertTrue({"engine-oil", "coolant-antifreeze", "washer-fluid", "wheel-hardware"}.issubset(ACTIVE_CATEGORY_META))

    def test_engine_oil_grade_and_formulation_combinations_are_searchable(self) -> None:
        rows = current_inventory_catalog(
            augment_equipment_catalog_rows(build_equipment_catalog_seed())
        )
        expected_oil_count = sum(len(grades) for _, grades in ENGINE_OIL_GRADES.values())
        self.assertEqual(expected_oil_count, 42)
        self.assertIn("full-synthetic-engine-oil-sae-0w-20", _matches(rows, "full synthetic 0w20"))
        self.assertIn("full-synthetic-engine-oil-sae-0w-12", _matches(rows, "0w12"))
        self.assertIn("high-mileage-synthetic-blend-engine-oil-sae-20w-50", _matches(rows, "high mileage 20w50"))
        self.assertIn("high-mileage-conventional-engine-oil-sae-10w-40", _matches(rows, "conventional high mileage 10w40"))

    def test_coolant_funnel_lug_nuts_and_refrigerant_specific_ac_equipment_are_covered(self) -> None:
        rows = current_inventory_catalog(
            augment_equipment_catalog_rows(build_equipment_catalog_seed())
        )
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


if __name__ == "__main__":
    unittest.main()
