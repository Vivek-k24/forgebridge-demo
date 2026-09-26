"""Add canonical specifications, limits, capacities, and measurements."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0041_specifications_limits"
down_revision: str | None = "0040_materials_consumables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"
SHARED_TABLES = "specification_definitions, vehicle_specification_values"


def upgrade() -> None:
    op.create_table(
        "specification_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("specification_key", sa.String(length=180), nullable=False),
        sa.Column("specification_type", sa.String(length=32), nullable=False),
        sa.Column("value_kind", sa.String(length=16), nullable=False),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column("quantity_kind", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "specification_type IN ('torque', 'pressure', 'flow', 'clearance', 'dimension', "
            "'capacity', 'service_limit', 'electrical', 'temperature', 'speed', 'time', "
            "'mass', 'volume', 'ratio', 'other')",
            name="ck_specification_definitions_type",
        ),
        sa.CheckConstraint(
            "value_kind IN ('scalar', 'range', 'maximum', 'minimum', 'text')",
            name="ck_specification_definitions_value_kind",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("specification_key"),
    )
    op.create_index(
        "ix_spec_definitions_type",
        "specification_definitions",
        ["specification_type"],
    )

    op.create_table(
        "vehicle_specification_values",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("specification_definition_id", sa.Uuid(), nullable=False),
        sa.Column("physical_entity_id", sa.Uuid(), nullable=True),
        sa.Column("material_definition_id", sa.Uuid(), nullable=True),
        sa.Column("application_key", sa.String(length=180), nullable=False),
        sa.Column("nominal_value", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("minimum_value", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("maximum_value", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("unit", sa.String(length=48), nullable=True),
        sa.Column("text_value", sa.String(length=255), nullable=True),
        sa.Column(
            "qualifier_key",
            sa.String(length=128),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "conditions",
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
            "nominal_value IS NOT NULL OR minimum_value IS NOT NULL OR maximum_value IS NOT NULL "
            "OR text_value IS NOT NULL",
            name="ck_vehicle_spec_values_has_value",
        ),
        sa.CheckConstraint(
            "minimum_value IS NULL OR maximum_value IS NULL OR minimum_value <= maximum_value",
            name="ck_vehicle_spec_values_range",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["specification_definition_id"],
            ["specification_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["physical_entity_id"],
            ["physical_entities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["material_definition_id"],
            ["material_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "vehicle_configuration_id",
            "specification_definition_id",
            "application_key",
            "qualifier_key",
            name="uq_vehicle_spec_values_scope",
        ),
    )
    op.create_index(
        "ix_vehicle_spec_values_vehicle",
        "vehicle_specification_values",
        ["vehicle_configuration_id", "specification_definition_id"],
    )
    op.create_index(
        "ix_vehicle_spec_values_entity",
        "vehicle_specification_values",
        ["physical_entity_id"],
    )
    op.create_index(
        "ix_vehicle_spec_values_material",
        "vehicle_specification_values",
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
        "ix_vehicle_spec_values_material",
        table_name="vehicle_specification_values",
    )
    op.drop_index(
        "ix_vehicle_spec_values_entity",
        table_name="vehicle_specification_values",
    )
    op.drop_index(
        "ix_vehicle_spec_values_vehicle",
        table_name="vehicle_specification_values",
    )
    op.drop_table("vehicle_specification_values")
    op.drop_index(
        "ix_spec_definitions_type",
        table_name="specification_definitions",
    )
    op.drop_table("specification_definitions")
