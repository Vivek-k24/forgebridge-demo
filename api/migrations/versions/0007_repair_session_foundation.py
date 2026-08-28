"""Add private resumable repair sessions, immutable events, and current projections."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_repair_session_foundation"
down_revision: str | None = "0006_user_vehicle_vin"
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
        "repair_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("user_vehicle_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("creation_idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("length(btrim(title)) BETWEEN 1 AND 160", name="ck_repair_sessions_title"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_vehicle_id"], ["user_vehicles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "creation_idempotency_key",
            name="uq_repair_sessions_owner_creation_key",
        ),
    )
    op.create_index("ix_repair_sessions_user_id", "repair_sessions", ["user_id"])
    op.create_index(
        "ix_repair_sessions_owner_vehicle_active",
        "repair_sessions",
        ["user_id", "user_vehicle_id", "archived_at"],
    )

    op.create_table(
        "repair_session_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("actor_device_id", sa.Uuid(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("sequence >= 1", name="ck_repair_session_events_sequence"),
        sa.CheckConstraint(
            "event_type IN ('session_started', 'session_paused', 'session_resumed', 'session_archived')",
            name="ck_repair_session_events_type",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["repair_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "sequence", name="uq_repair_session_events_sequence"),
        sa.UniqueConstraint(
            "session_id",
            "idempotency_key",
            name="uq_repair_session_events_idempotency",
        ),
    )
    op.create_index(
        "ix_repair_session_events_owner_session_sequence",
        "repair_session_events",
        ["user_id", "session_id", "sequence"],
    )

    op.create_table(
        "repair_session_projections",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("current_sequence", sa.BigInteger(), nullable=False),
        sa.Column("last_event_id", sa.Uuid(), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("editor_device_id", sa.Uuid(), nullable=True),
        sa.Column("editor_lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("projection_version", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'archived')",
            name="ck_repair_session_projections_status",
        ),
        sa.CheckConstraint("current_sequence >= 1", name="ck_repair_session_projections_sequence"),
        sa.CheckConstraint(
            "(editor_device_id IS NULL AND editor_lease_expires_at IS NULL) OR "
            "(editor_device_id IS NOT NULL AND editor_lease_expires_at IS NOT NULL)",
            name="ck_repair_session_projections_lease_pair",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["repair_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["last_event_id"],
            ["repair_session_events.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(
        "ix_repair_session_projections_user_id",
        "repair_session_projections",
        ["user_id"],
    )

    op.execute(
        sa.text(
            f"GRANT SELECT, INSERT, UPDATE ON repair_sessions, repair_session_projections TO {APP_ROLE}"
        )
    )
    op.execute(sa.text(f"GRANT SELECT, INSERT ON repair_session_events TO {APP_ROLE}"))
    _owner_policy("repair_sessions")
    _owner_policy("repair_session_events")
    _owner_policy("repair_session_projections")


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP POLICY IF EXISTS repair_session_projections_owner ON repair_session_projections"
        )
    )
    op.execute(
        sa.text("DROP POLICY IF EXISTS repair_session_events_owner ON repair_session_events")
    )
    op.execute(sa.text("DROP POLICY IF EXISTS repair_sessions_owner ON repair_sessions"))
    op.drop_index(
        "ix_repair_session_projections_user_id",
        table_name="repair_session_projections",
    )
    op.drop_table("repair_session_projections")
    op.drop_index(
        "ix_repair_session_events_owner_session_sequence",
        table_name="repair_session_events",
    )
    op.drop_table("repair_session_events")
    op.drop_index("ix_repair_sessions_owner_vehicle_active", table_name="repair_sessions")
    op.drop_index("ix_repair_sessions_user_id", table_name="repair_sessions")
    op.drop_table("repair_sessions")
