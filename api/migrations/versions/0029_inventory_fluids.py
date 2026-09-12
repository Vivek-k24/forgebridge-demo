"""Expand Inventory with fluids, wheel hardware, and refrigerant-specific A/C equipment."""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import insert

from partgraph.equipment.inventory_catalog_v2 import (
    KEYWORD_UPDATES,
    RETIRED_CATALOG_KEYS,
    catalog_additions,
)

revision: str = "0029_inventory_fluids"
down_revision: str | None = "0028_equipment_reference"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _catalog_table() -> sa.Table:
    metadata = sa.MetaData()
    return sa.Table(
        "equipment_catalog_items",
        metadata,
        sa.Column("id", sa.Uuid()),
        sa.Column("catalog_key", sa.String()),
        sa.Column("category", sa.String()),
        sa.Column("name", sa.String()),
        sa.Column("keywords", sa.String()),
        sa.Column("visual_key", sa.String()),
        sa.Column("is_active", sa.Boolean()),
    )


def upgrade() -> None:
    connection = op.get_bind()
    catalog = _catalog_table()

    connection.execute(
        sa.delete(catalog).where(catalog.c.catalog_key.in_(sorted(RETIRED_CATALOG_KEYS)))
    )

    for catalog_key, keywords in KEYWORD_UPDATES.items():
        result = connection.execute(
            sa.update(catalog)
            .where(catalog.c.catalog_key == catalog_key)
            .values(keywords=keywords)
        )
        if result.rowcount != 1:
            raise RuntimeError(f"inventory keyword target is missing: {catalog_key}")

    rows = [
        {
            "id": uuid5(NAMESPACE_URL, f"partgraph:equipment:{row['catalog_key']}"),
            **row,
            "is_active": True,
        }
        for row in catalog_additions()
    ]
    statement = insert(catalog).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[catalog.c.catalog_key],
        set_={
            "category": statement.excluded.category,
            "name": statement.excluded.name,
            "keywords": statement.excluded.keywords,
            "visual_key": statement.excluded.visual_key,
            "is_active": True,
        },
    )
    connection.execute(statement)


def downgrade() -> None:
    connection = op.get_bind()
    catalog = _catalog_table()

    addition_keys = [row["catalog_key"] for row in catalog_additions()]
    connection.execute(sa.delete(catalog).where(catalog.c.catalog_key.in_(addition_keys)))

    connection.execute(
        sa.update(catalog)
        .where(catalog.c.catalog_key == "coolant-funnel-kit")
        .values(keywords="fluid oil coolant brake service")
    )
    connection.execute(
        sa.update(catalog)
        .where(catalog.c.catalog_key == "spill-free-coolant-funnel")
        .values(keywords="fluid oil coolant brake service")
    )

    historical_rows = [
        {
            "id": uuid5(NAMESPACE_URL, "partgraph:equipment:a-c-refrigerant-recovery-recharge-machine"),
            "catalog_key": "a-c-refrigerant-recovery-recharge-machine",
            "category": "specialty-automotive",
            "name": "A/C refrigerant recovery/recharge machine",
            "keywords": (
                "Certified refrigerant recovery/recharge equipment AC A/C refrigerant "
                "recovery recharge service machine"
            ),
            "visual_key": "specialty",
            "is_active": True,
        },
        {
            "id": uuid5(NAMESPACE_URL, "partgraph:equipment:service-information-wiring-reference"),
            "catalog_key": "service-information-wiring-reference",
            "category": "other",
            "name": "Service information / wiring reference",
            "keywords": (
                "Service information / wiring reference repair manual wiring diagram "
                "service data reference"
            ),
            "visual_key": "other",
            "is_active": True,
        },
    ]
    statement = insert(catalog).values(historical_rows)
    statement = statement.on_conflict_do_nothing(index_elements=[catalog.c.catalog_key])
    connection.execute(statement)
