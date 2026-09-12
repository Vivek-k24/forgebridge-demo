import unittest
from collections import Counter

from partgraph.equipment.catalog_seed_v1 import (
    CATEGORY_LIMITS,
    CATEGORY_META,
    EXPECTED_ITEM_COUNT,
    build_equipment_catalog_seed,
)
from partgraph.equipment.service import _search_without_whitespace


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


if __name__ == "__main__":
    unittest.main()
