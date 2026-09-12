import unittest
from collections import Counter

from partgraph.equipment.catalog_seed_v1 import (
    CATEGORY_LIMITS,
    CATEGORY_META,
    EXPECTED_ITEM_COUNT,
    build_equipment_catalog_seed,
)
from partgraph.equipment.manual_reference_v1 import (
    MANUAL_REFERENCE_QUERY_TARGETS,
    REFERENCE_ADDITIONS,
    augment_equipment_catalog_rows,
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

    def test_manual_reference_equipment_is_searchable(self) -> None:
        rows = augment_equipment_catalog_rows(build_equipment_catalog_seed())
        self.assertEqual(len(rows), EXPECTED_ITEM_COUNT + len(REFERENCE_ADDITIONS))
        self.assertEqual(len({row["catalog_key"] for row in rows}), len(rows))

        for query, expected_keys in MANUAL_REFERENCE_QUERY_TARGETS.items():
            normalized_query = " ".join(query.strip().split()).lower()
            compact_query = _search_without_whitespace(normalized_query)
            matches = {
                row["catalog_key"]
                for row in rows
                if normalized_query in f"{row['name']} {row['keywords']}".lower()
                or compact_query
                in _search_without_whitespace(f"{row['name']} {row['keywords']}")
            }
            self.assertTrue(
                set(expected_keys).issubset(matches),
                f"manual equipment query is not fully covered: {query!r}",
            )


if __name__ == "__main__":
    unittest.main()
