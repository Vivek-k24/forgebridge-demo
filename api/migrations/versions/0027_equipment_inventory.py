"""Add shared equipment catalog and private owner inventory."""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

from partgraph.equipment.catalog_seed_v1 import EXPECTED_ITEM_COUNT, build_equipment_catalog_seed

revision: str = "0027_equipment_inventory"
down_revision: str | None = "0026_repair_completion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"


def upgrade() -> None:
    op.create_table(
        "equipment_catalog_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("catalog_key", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("keywords", sa.String(length=500), nullable=False),
        sa.Column("visual_key", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_key", name="uq_equipment_catalog_items_key"),
    )
    op.create_index("ix_equipment_catalog_items_category", "equipment_catalog_items", ["category", "name"])

    op.create_table(
        "owner_equipment_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_item_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("quantity >= 1 AND quantity <= 9999", name="ck_owner_equipment_items_quantity"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["catalog_item_id"], ["equipment_catalog_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "catalog_item_id", name="uq_owner_equipment_owner_catalog"),
    )
    op.create_index("ix_owner_equipment_items_owner", "owner_equipment_items", ["user_id", "catalog_item_id"])

    catalog_table = sa.table(
        "equipment_catalog_items",
        sa.column("id", sa.Uuid()),
        sa.column("catalog_key", sa.String()),
        sa.column("category", sa.String()),
        sa.column("name", sa.String()),
        sa.column("keywords", sa.String()),
        sa.column("visual_key", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    seed = build_equipment_catalog_seed()
    if len(seed) != EXPECTED_ITEM_COUNT:
        raise RuntimeError("equipment catalog seed count is not stable")
    op.bulk_insert(
        catalog_table,
        [
            {
                "id": uuid5(NAMESPACE_URL, f"partgraph:equipment:{row['catalog_key']}"),
                **row,
                "is_active": True,
            }
            for row in seed
        ],
    )

    op.execute(sa.text(f"GRANT SELECT ON equipment_catalog_items TO {APP_ROLE}"))
    op.execute(sa.text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON owner_equipment_items TO {APP_ROLE}"))
    op.execute(sa.text("ALTER TABLE owner_equipment_items ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE owner_equipment_items FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY owner_equipment_items_owner
            ON owner_equipment_items
            USING (user_id = NULLIF(current_setting('partgraph.user_id', true), '')::uuid)
            WITH CHECK (user_id = NULLIF(current_setting('partgraph.user_id', true), '')::uuid)
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP POLICY IF EXISTS owner_equipment_items_owner ON owner_equipment_items"))
    op.drop_index("ix_owner_equipment_items_owner", table_name="owner_equipment_items")
    op.drop_table("owner_equipment_items")
    op.drop_index("ix_equipment_catalog_items_category", table_name="equipment_catalog_items")
    op.drop_table("equipment_catalog_items")
