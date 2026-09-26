"""Add canonical hardware/fasteners and link private repair state."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0038_hardware_fasteners"
down_revision: str | None = "0037_physical_relationship_graph"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"
SHARED_TABLES = "hardware_definitions, hardware_part_identities, physical_entity_hardware"


def upgrade() -> None:
    op.create_table(
        "hardware_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hardware_key", sa.String(length=160), nullable=False),
        sa.Column("hardware_type", sa.String(length=24), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("nominal_size", sa.String(length=96), nullable=True),
        sa.Column("thread_spec", sa.String(length=64), nullable=True),
        sa.Column("nominal_diameter_mm", sa.Numeric(precision=8, scale=3), nullable=True),
        sa.Column("length_mm", sa.Numeric(precision=8, scale=3), nullable=True),
        sa.Column("drive_type", sa.String(length=64), nullable=True),
        sa.Column("head_style", sa.String(length=64), nullable=True),
        sa.Column("material", sa.String(length=96), nullable=True),
        sa.Column(
            "reuse_policy",
            sa.String(length=24),
            nullable=False,
            server_default="unknown",
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
            "hardware_type IN ('bolt', 'nut', 'screw', 'stud', 'washer', 'clip', "
            "'rivet', 'pin', 'clamp', 'seal', 'gasket', 'o_ring', 'retainer', "
            "'cotter_pin', 'spacer', 'spring', 'plug', 'other')",
            name="ck_hardware_definitions_type",
        ),
        sa.CheckConstraint(
            "reuse_policy IN ('unknown', 'reusable', 'replace_if_damaged', 'single_use')",
            name="ck_hardware_definitions_reuse_policy",
        ),
        sa.CheckConstraint(
            "nominal_diameter_mm IS NULL OR nominal_diameter_mm > 0",
            name="ck_hardware_definitions_nominal_diameter",
        ),
        sa.CheckConstraint(
            "length_mm IS NULL OR length_mm > 0",
            name="ck_hardware_definitions_length",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hardware_key"),
    )

    op.create_table(
        "hardware_part_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hardware_definition_id", sa.Uuid(), nullable=False),
        sa.Column("part_identity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["hardware_definition_id"],
            ["hardware_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["part_identity_id"],
            ["part_identities.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hardware_definition_id",
            "part_identity_id",
            name="uq_hardware_part_identities_mapping",
        ),
        sa.UniqueConstraint(
            "part_identity_id",
            name="uq_hardware_part_identities_part",
        ),
    )
    op.create_index(
        "ix_hardware_part_identities_hardware_definition_id",
        "hardware_part_identities",
        ["hardware_definition_id"],
    )
    op.create_index(
        "ix_hardware_part_identities_part_identity_id",
        "hardware_part_identities",
        ["part_identity_id"],
    )

    op.create_table(
        "physical_entity_hardware",
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "entity_kind",
            sa.String(length=24),
            nullable=False,
            server_default="hardware",
        ),
        sa.Column("hardware_definition_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "entity_kind = 'hardware'",
            name="ck_physical_entity_hardware_kind",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id", "entity_kind"],
            ["physical_entities.id", "physical_entities.entity_kind"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hardware_definition_id"],
            ["hardware_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("entity_id"),
        sa.UniqueConstraint("hardware_definition_id"),
    )

    op.add_column(
        "repair_fasteners",
        sa.Column("hardware_definition_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_repair_fasteners_hardware_definition_id",
        "repair_fasteners",
        "hardware_definitions",
        ["hardware_definition_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_repair_fasteners_hardware_definition_id",
        "repair_fasteners",
        ["hardware_definition_id"],
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
        "ix_repair_fasteners_hardware_definition_id",
        table_name="repair_fasteners",
    )
    op.drop_constraint(
        "fk_repair_fasteners_hardware_definition_id",
        "repair_fasteners",
        type_="foreignkey",
    )
    op.drop_column("repair_fasteners", "hardware_definition_id")
    op.drop_table("physical_entity_hardware")
    op.drop_index(
        "ix_hardware_part_identities_part_identity_id",
        table_name="hardware_part_identities",
    )
    op.drop_index(
        "ix_hardware_part_identities_hardware_definition_id",
        table_name="hardware_part_identities",
    )
    op.drop_table("hardware_part_identities")
    op.drop_table("hardware_definitions")
