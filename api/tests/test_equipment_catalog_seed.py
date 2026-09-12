from collections import Counter

from partgraph.equipment.catalog_seed_v1 import (
    CATEGORY_LIMITS,
    CATEGORY_META,
    EXPECTED_ITEM_COUNT,
    build_equipment_catalog_seed,
)


def test_equipment_catalog_seed_is_stable_and_unique() -> None:
    rows = build_equipment_catalog_seed()

    assert len(rows) == EXPECTED_ITEM_COUNT == 1107
    assert len({row["catalog_key"] for row in rows}) == EXPECTED_ITEM_COUNT
    assert all(row["name"].strip() for row in rows)
    assert all(row["category"] in CATEGORY_META for row in rows)

    counts = Counter(row["category"] for row in rows)
    assert counts == Counter(CATEGORY_LIMITS)
