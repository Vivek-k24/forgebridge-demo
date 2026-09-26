"""Add canonical fluids, materials, consumables, and exact applicability."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0040_materials_consumables"
down_revision: str | None = "0039_tools_equipment_workspace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"
SHARED_TABLES = (
    "material_definitions, vehicle_material_applicability, material_requirement_bindings"
)


def upgrade() -> None:
    op.create_table(
        "material_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("material_key", sa.String(length=160), nullable=False),
        sa.Column("material_type", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column("specification", sa.String(length=180), nullable=True),
        sa.Column("grade", sa.String(length=96), nullable=True),
        sa.Column("family", sa.String(length=96), nullable=True),
        sa.Column("is_consumed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "compatibility_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "safety_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "disposal_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "material_type IN ('engine_oil', 'transmission_fluid', 'gear_oil', 'coolant', "
            "'brake_fluid', 'power_steering_fluid', 'washer_fluid', 'refrigerant', "
            "'grease', 'sealant', 'adhesive', 'cleaner', 'anti_seize', 'threadlocker', "
            "'dielectric_grease', 'penetrant', 'absorbent', 'shop_consumable', 'other')",
            name="ck_material_definitions_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("material_key"),
    )
    op.create_index(
        "ix_material_definitions_material_type",
        "material_definitions",
        ["material_type"],
    )

    op.create_table(
        "vehicle_material_applicability",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("material_definition_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_structure_node_id", sa.Uuid(), nullable=True),
        sa.Column("application_key", sa.String(length=160), nullable=False),
        sa.Column("material_role", sa.String(length=32), nullable=False),
        sa.Column("applicability_state", sa.String(length=16), nullable=False),
        sa.Column(
            "qualifier_key",
            sa.String(length=128),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "qualifiers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "applicability_state IN ('compatible', 'incompatible', 'conditional')",
            name="ck_vehicle_material_applicability_state",
        ),
        sa.CheckConstraint(
            "material_role IN ('fill', 'lubricant', 'refrigerant_charge', 'cleaning', "
            "'assembly', 'sealing', 'thread_treatment', 'protection', 'consumable', 'other')",
            name="ck_vehicle_material_applicability_role",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["material_definition_id"],
            ["material_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_structure_node_id"],
            ["vehicle_structure_nodes.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "vehicle_configuration_id",
            "material_definition_id",
            "application_key",
            "material_role",
            "qualifier_key",
            name="uq_vehicle_material_applicability_edge",
        ),
    )
    op.create_index(
        "ix_vehicle_material_app_vehicle",
        "vehicle_material_applicability",
        ["vehicle_configuration_id", "applicability_state"],
    )
    op.create_index(
        "ix_vehicle_material_app_material",
        "vehicle_material_applicability",
        ["material_definition_id"],
    )

    op.create_table(
        "material_requirement_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requirement_definition_id", sa.Uuid(), nullable=False),
        sa.Column("material_definition_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["requirement_definition_id"],
            ["requirement_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["material_definition_id"],
            ["material_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "requirement_definition_id",
            name="uq_material_req_bindings_requirement",
        ),
    )
    op.create_index(
        "ix_material_req_bindings_material",
        "material_requirement_bindings",
        ["material_definition_id"],
    )

    op.execute(sa.text(f"GRANT SELECT ON {SHARED_TABLES} TO {APP_ROLE}, {REVIEWER_ROLE}"))
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON {SHARED_TABLES} FROM {APP_ROLE}, {REVIEWER_ROLE}"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"REVOKE SELECT ON {SHARED_TABLES} FROM {APP_ROLE}, {REVIEWER_ROLE}"))
    op.drop_index(
        "ix_material_req_bindings_material",
        table_name="material_requirement_bindings",
    )
    op.drop_table("material_requirement_bindings")
    op.drop_index(
        "ix_vehicle_material_app_material",
        table_name="vehicle_material_applicability",
    )
    op.drop_index(
        "ix_vehicle_material_app_vehicle",
        table_name="vehicle_material_applicability",
    )
    op.drop_table("vehicle_material_applicability")
    op.drop_index(
        "ix_material_definitions_material_type",
        table_name="material_definitions",
    )
    op.drop_table("material_definitions")
