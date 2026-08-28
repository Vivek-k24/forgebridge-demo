"""Add private fastener, inventory, observation, and photo-evidence memory."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_repair_memory"
down_revision: str | None = "0007_repair_session_foundation"
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
    op.drop_constraint(
        "ck_repair_session_events_type",
        "repair_session_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_repair_session_events_type",
        "repair_session_events",
        "event_type IN ("
        "'session_started', 'session_paused', 'session_resumed', 'session_archived', "
        "'storage_location_created', 'fastener_recorded', 'fastener_state_changed', "
        "'inventory_item_recorded', 'inventory_state_changed', 'observation_recorded', "
        "'photo_evidence_added', 'photo_evidence_deleted'"
        ")",
    )

    op.create_table(
        "repair_storage_locations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(label)) BETWEEN 1 AND 120",
            name="ck_repair_storage_locations_label",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["repair_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_repair_storage_locations_owner_session",
        "repair_storage_locations",
        ["user_id", "session_id", "created_at"],
    )

    op.create_table(
        "repair_fasteners",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("origin", sa.String(length=160), nullable=True),
        sa.Column("position", sa.String(length=160), nullable=True),
        sa.Column("physical_state", sa.String(length=16), nullable=False),
        sa.Column("storage_location_id", sa.Uuid(), nullable=True),
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
            "kind IN ('fastener', 'small_part')",
            name="ck_repair_fasteners_kind",
        ),
        sa.CheckConstraint(
            "physical_state IN ('installed', 'removed', 'stored', 'missing', 'damaged', 'replaced')",
            name="ck_repair_fasteners_state",
        ),
        sa.CheckConstraint(
            "length(btrim(label)) BETWEEN 1 AND 120",
            name="ck_repair_fasteners_label",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["repair_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["storage_location_id"],
            ["repair_storage_locations.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_repair_fasteners_owner_session_state",
        "repair_fasteners",
        ["user_id", "session_id", "physical_state", "created_at"],
    )

    op.create_table(
        "repair_inventory_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("procurement_state", sa.String(length=16), nullable=False),
        sa.Column("reference", sa.String(length=160), nullable=True),
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
        sa.CheckConstraint("quantity BETWEEN 1 AND 9999", name="ck_repair_inventory_quantity"),
        sa.CheckConstraint(
            "procurement_state IN ('needed', 'ordered', 'available', 'unavailable')",
            name="ck_repair_inventory_state",
        ),
        sa.CheckConstraint(
            "length(btrim(name)) BETWEEN 1 AND 160",
            name="ck_repair_inventory_name",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["repair_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_repair_inventory_owner_session_state",
        "repair_inventory_items",
        ["user_id", "session_id", "procurement_state", "created_at"],
    )

    op.create_table(
        "repair_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("text", sa.String(length=1000), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("review_state", sa.String(length=16), nullable=False),
        sa.Column("fastener_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ('general', 'condition', 'damage', 'part_number', 'before', 'after', "
            "'removed_part', 'current_step')",
            name="ck_repair_observations_category",
        ),
        sa.CheckConstraint(
            "source IN ('user', 'ai_proposed')",
            name="ck_repair_observations_source",
        ),
        sa.CheckConstraint(
            "review_state IN ('confirmed', 'proposed', 'rejected')",
            name="ck_repair_observations_review_state",
        ),
        sa.CheckConstraint(
            "length(btrim(text)) BETWEEN 1 AND 1000",
            name="ck_repair_observations_text",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["repair_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fastener_id"], ["repair_fasteners.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_repair_observations_owner_session_created",
        "repair_observations",
        ["user_id", "session_id", "created_at"],
    )

    op.create_table(
        "repair_photo_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("observation_id", sa.Uuid(), nullable=True),
        sa.Column("fastener_id", sa.Uuid(), nullable=True),
        sa.Column("storage_key", sa.String(length=80), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("media_type", sa.String(length=32), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('current_step', 'removed_part', 'fastener', 'damage', 'part_number', "
            "'before', 'after', 'general')",
            name="ck_repair_photo_evidence_purpose",
        ),
        sa.CheckConstraint("byte_size > 0", name="ck_repair_photo_evidence_size"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_repair_photo_evidence_sha256"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["repair_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["observation_id"], ["repair_observations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["fastener_id"], ["repair_fasteners.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_repair_photo_evidence_storage_key"),
    )
    op.create_index(
        "ix_repair_photo_evidence_owner_session_created",
        "repair_photo_evidence",
        ["user_id", "session_id", "deleted_at", "created_at"],
    )

    writable_tables = (
        "repair_storage_locations, repair_fasteners, repair_inventory_items, "
        "repair_observations, repair_photo_evidence"
    )
    op.execute(sa.text(f"GRANT SELECT, INSERT, UPDATE ON {writable_tables} TO {APP_ROLE}"))
    for table in (
        "repair_storage_locations",
        "repair_fasteners",
        "repair_inventory_items",
        "repair_observations",
        "repair_photo_evidence",
    ):
        _owner_policy(table)


def downgrade() -> None:
    for table in (
        "repair_photo_evidence",
        "repair_observations",
        "repair_inventory_items",
        "repair_fasteners",
        "repair_storage_locations",
    ):
        op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_owner ON {table}"))

    op.drop_index(
        "ix_repair_photo_evidence_owner_session_created",
        table_name="repair_photo_evidence",
    )
    op.drop_table("repair_photo_evidence")
    op.drop_index(
        "ix_repair_observations_owner_session_created",
        table_name="repair_observations",
    )
    op.drop_table("repair_observations")
    op.drop_index(
        "ix_repair_inventory_owner_session_state",
        table_name="repair_inventory_items",
    )
    op.drop_table("repair_inventory_items")
    op.drop_index(
        "ix_repair_fasteners_owner_session_state",
        table_name="repair_fasteners",
    )
    op.drop_table("repair_fasteners")
    op.drop_index(
        "ix_repair_storage_locations_owner_session",
        table_name="repair_storage_locations",
    )
    op.drop_table("repair_storage_locations")

    op.drop_constraint(
        "ck_repair_session_events_type",
        "repair_session_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_repair_session_events_type",
        "repair_session_events",
        "event_type IN ("
        "'session_started', 'session_paused', 'session_resumed', 'session_archived'"
        ")",
    )
