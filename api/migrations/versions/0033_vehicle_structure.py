"""Add canonical vehicle system and assembly hierarchy."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033_vehicle_structure"
down_revision: str | None = "0032_shared_read_privileges"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"


def upgrade() -> None:
    op.create_table(
        "vehicle_structure_nodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("node_key", sa.String(length=160), nullable=False),
        sa.Column("node_type", sa.String(length=24), nullable=False),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column("parent_node_id", sa.Uuid(), nullable=True),
        sa.Column("placement", sa.String(length=96), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "node_type IN ('system', 'subsystem', 'assembly', 'subassembly')",
            name="ck_vehicle_structure_nodes_type",
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_vehicle_structure_nodes_position",
        ),
        sa.CheckConstraint(
            "parent_node_id IS NULL OR parent_node_id <> id",
            name="ck_vehicle_structure_nodes_not_self_parent",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_node_id"],
            ["vehicle_structure_nodes.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "vehicle_configuration_id",
            "node_key",
            name="uq_vehicle_structure_nodes_vehicle_key",
        ),
    )
    op.create_index(
        "ix_vehicle_structure_nodes_vehicle_configuration_id",
        "vehicle_structure_nodes",
        ["vehicle_configuration_id"],
    )
    op.create_index(
        "ix_vehicle_structure_nodes_parent_node_id",
        "vehicle_structure_nodes",
        ["parent_node_id"],
    )
    op.create_index(
        "ix_vehicle_structure_nodes_vehicle_parent_position",
        "vehicle_structure_nodes",
        ["vehicle_configuration_id", "parent_node_id", "position"],
    )

    op.execute(sa.text(f"GRANT SELECT ON vehicle_structure_nodes TO {APP_ROLE}"))
    op.execute(sa.text(f"GRANT SELECT ON vehicle_structure_nodes TO {REVIEWER_ROLE}"))
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON vehicle_structure_nodes FROM {APP_ROLE}, {REVIEWER_ROLE}"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"REVOKE SELECT ON vehicle_structure_nodes FROM {APP_ROLE}"))
    op.execute(sa.text(f"REVOKE SELECT ON vehicle_structure_nodes FROM {REVIEWER_ROLE}"))
    op.drop_index(
        "ix_vehicle_structure_nodes_vehicle_parent_position",
        table_name="vehicle_structure_nodes",
    )
    op.drop_index(
        "ix_vehicle_structure_nodes_parent_node_id",
        table_name="vehicle_structure_nodes",
    )
    op.drop_index(
        "ix_vehicle_structure_nodes_vehicle_configuration_id",
        table_name="vehicle_structure_nodes",
    )
    op.drop_table("vehicle_structure_nodes")
