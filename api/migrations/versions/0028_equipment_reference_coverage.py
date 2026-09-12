"""Cover the generic equipment terms used by the current repair reference."""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import insert

from partgraph.equipment.manual_reference_v1 import (
    REFERENCE_ADDITIONS,
    REFERENCE_ALIASES,
    REFERENCE_BASE_KEYWORDS,
    reference_keywords,
)

revision: str = "0028_equipment_reference_coverage"
down_revision: str | None = "0027_equipment_inventory"
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

    for catalog_key in REFERENCE_ALIASES:
        result = connection.execute(
            sa.update(catalog)
            .where(catalog.c.catalog_key == catalog_key)
            .values(keywords=reference_keywords(catalog_key))
        )
        if result.rowcount != 1:
            raise RuntimeError(f"equipment reference alias target is missing: {catalog_key}")

    rows = [
        {
            "id": uuid5(NAMESPACE_URL, f"partgraph:equipment:{row['catalog_key']}"),
            **row,
            "is_active": True,
        }
        for row in REFERENCE_ADDITIONS
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

    addition_keys = [row["catalog_key"] for row in REFERENCE_ADDITIONS]
    connection.execute(sa.delete(catalog).where(catalog.c.catalog_key.in_(addition_keys)))

    for catalog_key, base_keywords in REFERENCE_BASE_KEYWORDS.items():
        connection.execute(
            sa.update(catalog)
            .where(catalog.c.catalog_key == catalog_key)
            .values(keywords=base_keywords)
        )
