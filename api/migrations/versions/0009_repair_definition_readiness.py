"""Add verified repair definitions, requirement manifests, and private readiness."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_repair_definition_readiness"
down_revision: str | None = "0008_repair_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"


def _owner_policy(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY {table}_owner
            ON {table}
            USING (
                user_id = NULLIF(current_setting('partgraph.user_id', true), '')::uuid
            )
            WITH CHECK (
                user_id = NULLIF(current_setting('partgraph.user_id', true), '')::uuid
            )
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "catalog_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_key", sa.String(length=96), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("source_class", sa.String(length=32), nullable=False),
        sa.Column(
            "license_status",
            sa.String(length=16),
            server_default="unreviewed",
            nullable=False,
        ),
        sa.Column("automation_allowed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("terms_url", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_class IN ('government', 'oem_service', 'licensed_oem_derived', "
            "'oem_parts', 'industry_standard', 'retailer', 'community')",
            name="ck_catalog_sources_class",
        ),
        sa.CheckConstraint(
            "license_status IN ('unreviewed', 'approved', 'prohibited')",
            name="ck_catalog_sources_license_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key", name="uq_catalog_sources_source_key"),
    )

    op.create_table(
        "mechanical_claims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("verified_evidence_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_configuration_id", sa.Uuid(), nullable=True),
        sa.Column("claim_domain", sa.String(length=32), nullable=False),
        sa.Column("claim_risk", sa.String(length=24), nullable=False),
        sa.Column("normalized_key", sa.String(length=160), nullable=False),
        sa.Column("repair_key", sa.String(length=120), nullable=True),
        sa.Column("claim_payload", sa.JSON(), nullable=False),
        sa.Column("explicit_claim", sa.Boolean(), nullable=False),
        sa.Column("exact_applicability", sa.Boolean(), nullable=False),
        sa.Column("promotion_state", sa.String(length=24), nullable=False),
        sa.Column("conflict_key", sa.String(length=128), nullable=True),
        sa.Column("superseded_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            "claim_domain IN ('vehicle_identity', 'safety_campaign', "
            "'repair_requirement', 'part_fitment')",
            name="ck_mechanical_claims_domain",
        ),
        sa.CheckConstraint(
            "claim_risk IN ('normal', 'safety_critical')",
            name="ck_mechanical_claims_risk",
        ),
        sa.CheckConstraint(
            "promotion_state IN ('staged', 'needs_review', 'verified', 'rejected', "
            "'conflict', 'superseded')",
            name="ck_mechanical_claims_promotion_state",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["catalog_sources.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["verified_evidence_id"],
            ["catalog_verified_evidence.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_id"], ["mechanical_claims.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mechanical_claims_conflict_key",
        "mechanical_claims",
        ["conflict_key"],
    )
    op.create_index(
        "ix_mechanical_claims_vehicle_domain",
        "mechanical_claims",
        ["vehicle_configuration_id", "claim_domain", "promotion_state"],
    )

    op.create_table(
        "repair_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("repair_key", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'verified', 'superseded')",
            name="ck_repair_definitions_status",
        ),
        sa.CheckConstraint("version >= 1", name="ck_repair_definitions_version"),
        sa.ForeignKeyConstraint(
            ["vehicle_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_id"], ["repair_definitions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "vehicle_configuration_id",
            "repair_key",
            "version",
            name="uq_repair_definitions_vehicle_key_version",
        ),
    )
    op.create_index(
        "ix_repair_definitions_vehicle_status",
        "repair_definitions",
        ["vehicle_configuration_id", "status", "repair_key"],
    )

    op.create_table(
        "repair_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repair_definition_id", sa.Uuid(), nullable=False),
        sa.Column("operation_key", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("position >= 0", name="ck_repair_operations_position"),
        sa.ForeignKeyConstraint(
            ["repair_definition_id"], ["repair_definitions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repair_definition_id",
            "operation_key",
            name="uq_repair_operations_definition_key",
        ),
    )
    op.create_index(
        "ix_repair_operations_definition_position",
        "repair_operations",
        ["repair_definition_id", "position"],
    )

    op.create_table(
        "requirement_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requirement_key", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column("default_unit", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ('tool', 'equipment', 'part', 'fluid', 'consumable', "
            "'hardware', 'workspace', 'safety_prerequisite')",
            name="ck_requirement_definitions_category",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "requirement_key", name="uq_requirement_definitions_requirement_key"
        ),
    )
    op.create_index(
        "ix_requirement_definitions_category",
        "requirement_definitions",
        ["category"],
    )

    op.create_table(
        "requirement_uses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repair_definition_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=True),
        sa.Column("requirement_definition_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("necessity", sa.String(length=16), nullable=False),
        sa.Column("fulfillment_mode", sa.String(length=24), nullable=False),
        sa.Column("timing", sa.String(length=24), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "necessity IN ('required', 'recommended')",
            name="ck_requirement_uses_necessity",
        ),
        sa.CheckConstraint(
            "fulfillment_mode IN ('reusable', 'consumed', 'reuse_existing', "
            "'replacement_required', 'replace_if_damaged')",
            name="ck_requirement_uses_fulfillment_mode",
        ),
        sa.CheckConstraint(
            "timing IN ('before_start', 'whole_repair', 'operation')",
            name="ck_requirement_uses_timing",
        ),
        sa.CheckConstraint(
            "quantity IS NULL OR quantity > 0",
            name="ck_requirement_uses_quantity",
        ),
        sa.CheckConstraint(
            "(timing = 'operation' AND operation_id IS NOT NULL) OR "
            "(timing <> 'operation')",
            name="ck_requirement_uses_operation_scope",
        ),
        sa.ForeignKeyConstraint(
            ["repair_definition_id"], ["repair_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"], ["repair_operations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requirement_definition_id"],
            ["requirement_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_requirement_uses_definition_requirement",
        "requirement_uses",
        ["repair_definition_id", "requirement_definition_id", "operation_id"],
    )

    op.create_table(
        "requirement_use_evidence",
        sa.Column("requirement_use_id", sa.Uuid(), nullable=False),
        sa.Column("mechanical_claim_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["requirement_use_id"], ["requirement_uses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["mechanical_claim_id"], ["mechanical_claims.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("requirement_use_id", "mechanical_claim_id"),
    )

    op.add_column(
        "repair_sessions",
        sa.Column("repair_definition_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_repair_sessions_repair_definition_id",
        "repair_sessions",
        "repair_definitions",
        ["repair_definition_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_repair_sessions_repair_definition_id",
        "repair_sessions",
        ["repair_definition_id"],
    )

    op.create_table(
        "user_garage_inventory_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_definition_id", sa.Uuid(), nullable=False),
        sa.Column(
            "quantity_available",
            sa.Numeric(precision=12, scale=3),
            server_default="0",
            nullable=False,
        ),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity_available >= 0",
            name="ck_user_garage_inventory_quantity",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["requirement_definition_id"],
            ["requirement_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "requirement_definition_id",
            name="uq_user_garage_inventory_requirement",
        ),
    )
    op.create_index(
        "ix_user_garage_inventory_items_user_id",
        "user_garage_inventory_items",
        ["user_id"],
    )

    op.create_table(
        "repair_requirement_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_use_id", sa.Uuid(), nullable=False),
        sa.Column(
            "quantity_available",
            sa.Numeric(precision=12, scale=3),
            server_default="0",
            nullable=False,
        ),
        sa.Column("readiness_state", sa.String(length=16), nullable=False),
        sa.Column("procurement_reference", sa.String(length=240), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "readiness_state IN ('have', 'missing', 'ordered', 'unavailable')",
            name="ck_repair_requirement_states_state",
        ),
        sa.CheckConstraint(
            "quantity_available >= 0",
            name="ck_repair_requirement_states_quantity",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["repair_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requirement_use_id"], ["requirement_uses.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "session_id",
            "requirement_use_id",
            name="uq_repair_requirement_states_session_requirement",
        ),
    )
    op.create_index(
        "ix_repair_requirement_states_owner_session",
        "repair_requirement_states",
        ["user_id", "session_id", "readiness_state"],
    )

    shared_tables = (
        "catalog_sources, mechanical_claims, repair_definitions, repair_operations, "
        "requirement_definitions, requirement_uses, requirement_use_evidence"
    )
    op.execute(sa.text(f"GRANT SELECT ON {shared_tables} TO {APP_ROLE}"))
    op.execute(
        sa.text(
            "GRANT SELECT, INSERT, UPDATE ON user_garage_inventory_items, "
            f"repair_requirement_states TO {APP_ROLE}"
        )
    )
    _owner_policy("user_garage_inventory_items")
    _owner_policy("repair_requirement_states")


def downgrade() -> None:
    for table in ("repair_requirement_states", "user_garage_inventory_items"):
        op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_owner ON {table}"))

    op.drop_index(
        "ix_repair_requirement_states_owner_session",
        table_name="repair_requirement_states",
    )
    op.drop_table("repair_requirement_states")
    op.drop_index(
        "ix_user_garage_inventory_items_user_id",
        table_name="user_garage_inventory_items",
    )
    op.drop_table("user_garage_inventory_items")

    op.drop_index(
        "ix_repair_sessions_repair_definition_id",
        table_name="repair_sessions",
    )
    op.drop_constraint(
        "fk_repair_sessions_repair_definition_id",
        "repair_sessions",
        type_="foreignkey",
    )
    op.drop_column("repair_sessions", "repair_definition_id")

    op.drop_table("requirement_use_evidence")
    op.drop_index(
        "ix_requirement_uses_definition_requirement",
        table_name="requirement_uses",
    )
    op.drop_table("requirement_uses")
    op.drop_index(
        "ix_requirement_definitions_category",
        table_name="requirement_definitions",
    )
    op.drop_table("requirement_definitions")
    op.drop_index(
        "ix_repair_operations_definition_position",
        table_name="repair_operations",
    )
    op.drop_table("repair_operations")
    op.drop_index(
        "ix_repair_definitions_vehicle_status",
        table_name="repair_definitions",
    )
    op.drop_table("repair_definitions")
    op.drop_index(
        "ix_mechanical_claims_vehicle_domain",
        table_name="mechanical_claims",
    )
    op.drop_index("ix_mechanical_claims_conflict_key", table_name="mechanical_claims")
    op.drop_table("mechanical_claims")
    op.drop_table("catalog_sources")
