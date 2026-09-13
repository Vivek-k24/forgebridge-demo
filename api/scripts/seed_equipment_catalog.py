from __future__ import annotations

import os
from uuid import NAMESPACE_URL, uuid5

import psycopg

from partgraph.equipment.catalog_seed_v1 import build_equipment_catalog_seed
from partgraph.equipment.inventory_catalog_v2 import (
    RETIRED_CATALOG_KEYS,
    current_inventory_catalog,
)
from partgraph.equipment.manual_reference_v1 import augment_equipment_catalog_rows

EXPECTED_CURRENT_CATALOG_ITEMS = 1178
DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def _current_rows() -> list[dict[str, object]]:
    rows = current_inventory_catalog(
        augment_equipment_catalog_rows(build_equipment_catalog_seed())
    )
    if len(rows) != EXPECTED_CURRENT_CATALOG_ITEMS:
        raise RuntimeError(
            "equipment seed catalog size drifted: "
            f"expected {EXPECTED_CURRENT_CATALOG_ITEMS}, got {len(rows)}"
        )

    return [
        {
            "id": uuid5(NAMESPACE_URL, f"partgraph:equipment:{row['catalog_key']}"),
            **row,
            "is_active": True,
        }
        for row in rows
    ]


def seed_equipment_catalog(connection: psycopg.Connection[object]) -> int:
    rows = _current_rows()
    catalog_keys = [str(row["catalog_key"]) for row in rows]

    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO equipment_catalog_items (
                id,
                catalog_key,
                category,
                name,
                keywords,
                visual_key,
                is_active
            )
            VALUES (
                %(id)s,
                %(catalog_key)s,
                %(category)s,
                %(name)s,
                %(keywords)s,
                %(visual_key)s,
                %(is_active)s
            )
            ON CONFLICT (catalog_key) DO UPDATE SET
                category = EXCLUDED.category,
                name = EXCLUDED.name,
                keywords = EXCLUDED.keywords,
                visual_key = EXCLUDED.visual_key,
                is_active = EXCLUDED.is_active
            """,
            rows,
        )
        cursor.execute(
            """
            UPDATE equipment_catalog_items
               SET is_active = false
             WHERE catalog_key = ANY(%s)
            """,
            (sorted(RETIRED_CATALOG_KEYS),),
        )
        cursor.execute(
            """
            SELECT count(*)
              FROM equipment_catalog_items
             WHERE is_active = true
               AND catalog_key = ANY(%s)
            """,
            (catalog_keys,),
        )
        active_seeded = int(cursor.fetchone()[0])

    if active_seeded != EXPECTED_CURRENT_CATALOG_ITEMS:
        raise RuntimeError(
            "equipment seed verification failed: "
            f"expected {EXPECTED_CURRENT_CATALOG_ITEMS} active seeded rows, "
            f"got {active_seeded}"
        )
    return active_seeded


def main() -> int:
    with psycopg.connect(_database_url()) as connection:
        count = seed_equipment_catalog(connection)
    print(f"seeded {count} active equipment catalog items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
