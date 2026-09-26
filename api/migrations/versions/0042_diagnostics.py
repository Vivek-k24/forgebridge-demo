"""Add canonical diagnostics, inspections, and cause relationships."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0042_diagnostics"
down_revision: str | None = "0041_specifications_limits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"
SHARED_TABLES = (
    "diagnostic_signal_definitions, vehicle_diagnostic_signals, "
    "diagnostic_inspection_definitions, vehicle_diagnostic_inspections, "
    "diagnostic_cause_relationships"
)


def upgrade() -> None:
    op.create_table(
        "diagnostic_signal_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("signal_key", sa.String(length=180), nullable=False),
        sa.Column("signal_type", sa.String(length=16), nullable=False),
        sa.Column("code", sa.String(length=24), nullable=True),
        sa.Column("code_system", sa.String(length=24), nullable=True),
        sa.Column("family", sa.String(length=64), nullable=True),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "signal_type IN ('symptom', 'dtc')",
            name="ck_diagnostic_signal_definitions_type",
        ),
        sa.CheckConstraint(
            "(signal_type = 'dtc' AND code IS NOT NULL AND code_system IS NOT NULL) OR "
            "(signal_type = 'symptom' AND code IS NULL AND code_system IS NULL)",
            name="ck_diagnostic_signal_definitions_code_scope",
        ),
        sa.CheckConstraint(
            "code_system IS NULL OR code_system IN ('obd2', 'manufacturer', 'other')",
            name="ck_diagnostic_signal_definitions_code_system",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("signal_key"),
    )
    op.create_index(
        "ix_diagnostic_signal_definitions_type",
        "diagnostic_signal_definitions",
        ["signal_type"],
    )

    op.create_table(
        "vehicle_diagnostic_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("signal_definition_id", sa.Uuid(), nullable=False),
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
            name="ck_vehicle_diagnostic_signals_state",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["signal_definition_id"],
            ["diagnostic_signal_definitions.id"],
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
            "signal_definition_id",
            "application_key",
            "qualifier_key",
            name="uq_vehicle_diagnostic_signals_scope",
        ),
    )
    op.create_index(
        "ix_vehicle_diagnostic_signals_vehicle",
        "vehicle_diagnostic_signals",
        ["vehicle_configuration_id", "applicability_state"],
    )
    op.create_index(
        "ix_vehicle_diagnostic_signals_definition",
        "vehicle_diagnostic_signals",
        ["signal_definition_id"],
    )

    op.create_table(
        "diagnostic_inspection_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("inspection_key", sa.String(length=180), nullable=False),
        sa.Column("inspection_type", sa.String(length=24), nullable=False),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("specification_definition_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "inspection_type IN ('visual', 'functional', 'measurement', 'leak', 'pressure', "
            "'electrical', 'continuity', 'other')",
            name="ck_diagnostic_inspection_definitions_type",
        ),
        sa.ForeignKeyConstraint(
            ["specification_definition_id"],
            ["specification_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inspection_key"),
    )
    op.create_index(
        "ix_diagnostic_inspection_definitions_type",
        "diagnostic_inspection_definitions",
        ["inspection_type"],
    )

    op.create_table(
        "vehicle_diagnostic_inspections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("inspection_definition_id", sa.Uuid(), nullable=False),
        sa.Column("physical_entity_id", sa.Uuid(), nullable=True),
        sa.Column("expected_specification_value_id", sa.Uuid(), nullable=True),
        sa.Column("application_key", sa.String(length=180), nullable=False),
        sa.Column("expected_result_text", sa.String(length=500), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["vehicle_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_definition_id"],
            ["diagnostic_inspection_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["physical_entity_id"],
            ["physical_entities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["expected_specification_value_id"],
            ["vehicle_specification_values.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "vehicle_configuration_id",
            "inspection_definition_id",
            "application_key",
            "qualifier_key",
            name="uq_vehicle_diagnostic_inspections_scope",
        ),
    )
    op.create_index(
        "ix_vehicle_diagnostic_inspections_vehicle",
        "vehicle_diagnostic_inspections",
        ["vehicle_configuration_id", "inspection_definition_id"],
    )

    op.create_table(
        "diagnostic_cause_relationships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_diagnostic_signal_id", sa.Uuid(), nullable=False),
        sa.Column("target_physical_entity_id", sa.Uuid(), nullable=False),
        sa.Column("cause_state", sa.String(length=16), nullable=False),
        sa.Column(
            "qualifier_key",
            sa.String(length=128),
            nullable=False,
            server_default="",
        ),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "cause_state IN ('suspected', 'confirmed', 'excluded')",
            name="ck_diagnostic_cause_relationships_state",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_diagnostic_signal_id"],
            ["vehicle_diagnostic_signals.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_physical_entity_id"],
            ["physical_entities.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "vehicle_configuration_id",
            "vehicle_diagnostic_signal_id",
            "target_physical_entity_id",
            "qualifier_key",
            name="uq_diagnostic_cause_relationships_edge",
        ),
    )
    op.create_index(
        "ix_diagnostic_cause_relationships_vehicle",
        "diagnostic_cause_relationships",
        ["vehicle_configuration_id", "cause_state"],
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
        "ix_diagnostic_cause_relationships_vehicle",
        table_name="diagnostic_cause_relationships",
    )
    op.drop_table("diagnostic_cause_relationships")
    op.drop_index(
        "ix_vehicle_diagnostic_inspections_vehicle",
        table_name="vehicle_diagnostic_inspections",
    )
    op.drop_table("vehicle_diagnostic_inspections")
    op.drop_index(
        "ix_diagnostic_inspection_definitions_type",
        table_name="diagnostic_inspection_definitions",
    )
    op.drop_table("diagnostic_inspection_definitions")
    op.drop_index(
        "ix_vehicle_diagnostic_signals_definition",
        table_name="vehicle_diagnostic_signals",
    )
    op.drop_index(
        "ix_vehicle_diagnostic_signals_vehicle",
        table_name="vehicle_diagnostic_signals",
    )
    op.drop_table("vehicle_diagnostic_signals")
    op.drop_index(
        "ix_diagnostic_signal_definitions_type",
        table_name="diagnostic_signal_definitions",
    )
    op.drop_table("diagnostic_signal_definitions")
