"""Add canonical electrical, sensor, connector, and pin-level graph data."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0043_electrical"
down_revision: str | None = "0042_diagnostics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"
SHARED_TABLES = (
    "electrical_definitions, physical_entity_electrical, vehicle_electrical_applicability, "
    "connector_pin_definitions, vehicle_electrical_connections"
)


def upgrade() -> None:
    op.create_table(
        "electrical_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("electrical_key", sa.String(length=180), nullable=False),
        sa.Column("electrical_type", sa.String(length=24), nullable=False),
        sa.Column("control_class", sa.String(length=24), nullable=False),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
            "electrical_type IN ('sensor', 'actuator', 'connector', 'lamp', 'switch', 'fuse', "
            "'relay', 'ground', 'control_module', 'circuit', 'service_interface', 'other')",
            name="ck_electrical_definitions_type",
        ),
        sa.CheckConstraint(
            "control_class IN ('passive', 'sensor_input', 'actuator_output', 'control_module', "
            "'network', 'service_interface', 'high_voltage', 'other')",
            name="ck_electrical_definitions_control_class",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("electrical_key"),
        sa.UniqueConstraint(
            "id",
            "electrical_type",
            name="uq_electrical_definitions_id_type",
        ),
    )
    op.create_index(
        "ix_electrical_definitions_type",
        "electrical_definitions",
        ["electrical_type"],
    )
    op.create_index(
        "ix_electrical_definitions_control_class",
        "electrical_definitions",
        ["control_class"],
    )

    op.create_table(
        "physical_entity_electrical",
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "entity_kind",
            sa.String(length=24),
            nullable=False,
            server_default="electrical",
        ),
        sa.Column("electrical_definition_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "entity_kind = 'electrical'",
            name="ck_physical_entity_electrical_kind",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id", "entity_kind"],
            ["physical_entities.id", "physical_entities.entity_kind"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["electrical_definition_id"],
            ["electrical_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("entity_id"),
        sa.UniqueConstraint("electrical_definition_id"),
    )

    op.create_table(
        "vehicle_electrical_applicability",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("electrical_definition_id", sa.Uuid(), nullable=False),
        sa.Column("physical_entity_id", sa.Uuid(), nullable=True),
        sa.Column("application_key", sa.String(length=180), nullable=False),
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
            "applicability_state IN ('applicable', 'excluded', 'conditional')",
            name="ck_vehicle_electrical_applicability_state",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["electrical_definition_id"],
            ["electrical_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["physical_entity_id"],
            ["physical_entities.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "vehicle_configuration_id",
            "electrical_definition_id",
            "application_key",
            "qualifier_key",
            name="uq_vehicle_electrical_applicability_scope",
        ),
    )
    op.create_index(
        "ix_vehicle_electrical_app_vehicle",
        "vehicle_electrical_applicability",
        ["vehicle_configuration_id", "applicability_state"],
    )

    op.create_table(
        "connector_pin_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connector_definition_id", sa.Uuid(), nullable=False),
        sa.Column(
            "connector_electrical_type",
            sa.String(length=24),
            nullable=False,
            server_default="connector",
        ),
        sa.Column("pin_key", sa.String(length=96), nullable=False),
        sa.Column("pin_label", sa.String(length=96), nullable=True),
        sa.Column("circuit_role", sa.String(length=96), nullable=True),
        sa.Column("terminal_type", sa.String(length=96), nullable=True),
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
            "connector_electrical_type = 'connector'",
            name="ck_connector_pin_definitions_parent_type",
        ),
        sa.ForeignKeyConstraint(
            ["connector_definition_id", "connector_electrical_type"],
            ["electrical_definitions.id", "electrical_definitions.electrical_type"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connector_definition_id",
            "pin_key",
            name="uq_connector_pin_definitions_connector_key",
        ),
    )

    op.create_table(
        "vehicle_electrical_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("source_pin_id", sa.Uuid(), nullable=False),
        sa.Column("target_pin_id", sa.Uuid(), nullable=False),
        sa.Column("connection_type", sa.String(length=16), nullable=False),
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
            "source_pin_id <> target_pin_id",
            name="ck_vehicle_electrical_connections_not_self",
        ),
        sa.CheckConstraint(
            "connection_type IN ('signal', 'power', 'ground', 'control', 'lighting', "
            "'network', 'other')",
            name="ck_vehicle_electrical_connections_type",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_pin_id"],
            ["connector_pin_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_pin_id"],
            ["connector_pin_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "vehicle_configuration_id",
            "source_pin_id",
            "target_pin_id",
            "connection_type",
            "qualifier_key",
            name="uq_vehicle_electrical_connections_edge",
        ),
    )
    op.create_index(
        "ix_vehicle_electrical_connections_vehicle",
        "vehicle_electrical_connections",
        ["vehicle_configuration_id", "connection_type"],
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
        "ix_vehicle_electrical_connections_vehicle",
        table_name="vehicle_electrical_connections",
    )
    op.drop_table("vehicle_electrical_connections")
    op.drop_table("connector_pin_definitions")
    op.drop_index(
        "ix_vehicle_electrical_app_vehicle",
        table_name="vehicle_electrical_applicability",
    )
    op.drop_table("vehicle_electrical_applicability")
    op.drop_table("physical_entity_electrical")
    op.drop_index(
        "ix_electrical_definitions_control_class",
        table_name="electrical_definitions",
    )
    op.drop_index(
        "ix_electrical_definitions_type",
        table_name="electrical_definitions",
    )
    op.drop_table("electrical_definitions")
