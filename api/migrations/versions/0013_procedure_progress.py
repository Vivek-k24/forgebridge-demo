"""Add private guided-procedure progress and session event support."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_procedure_progress"
down_revision: str | None = "0012_verified_procedure_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"

_PREVIOUS_EVENT_TYPES = (
    "'session_started', 'session_paused', 'session_resumed', 'session_archived', "
    "'storage_location_created', 'fastener_recorded', 'fastener_state_changed', "
    "'inventory_item_recorded', 'inventory_state_changed', 'observation_recorded', "
    "'photo_evidence_added', 'photo_evidence_deleted', 'readiness_state_changed'"
)


def _replace_event_type_constraint(event_types: str) -> None:
    op.drop_constraint(
        "ck_repair_session_events_type",
        "repair_session_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_repair_session_events_type",
        "repair_session_events",
        f"event_type IN ({event_types})",
    )


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
    op.add_column(
        "procedure_actions",
        sa.Column(
            "skippable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_table(
        "repair_procedure_action_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("progress_state", sa.String(length=16), nullable=False),
        sa.Column("blocker_code", sa.String(length=64), nullable=True),
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
            "progress_state IN ('completed', 'skipped', 'blocked')",
            name="ck_repair_procedure_action_states_progress",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["repair_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["action_id"], ["procedure_actions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "session_id",
            "action_id",
            name="uq_repair_procedure_action_states_owner_session_action",
        ),
    )
    op.create_index(
        "ix_repair_procedure_action_states_owner_session",
        "repair_procedure_action_states",
        ["user_id", "session_id", "progress_state"],
    )

    op.execute(
        sa.text(
            "GRANT SELECT ON repair_capability_policies, procedure_actions, "
            "procedure_action_dependencies, procedure_action_requirement_uses, "
            f"procedure_action_evidence TO {APP_ROLE}"
        )
    )
    op.execute(
        sa.text(
            "GRANT SELECT, INSERT, UPDATE ON repair_procedure_action_states "
            f"TO {APP_ROLE}"
        )
    )
    _owner_policy("repair_procedure_action_states")
    _replace_event_type_constraint(
        f"{_PREVIOUS_EVENT_TYPES}, 'procedure_action_state_changed'"
    )


def downgrade() -> None:
    _replace_event_type_constraint(_PREVIOUS_EVENT_TYPES)
    op.execute(
        sa.text(
            "DROP POLICY IF EXISTS repair_procedure_action_states_owner "
            "ON repair_procedure_action_states"
        )
    )
    op.drop_index(
        "ix_repair_procedure_action_states_owner_session",
        table_name="repair_procedure_action_states",
    )
    op.drop_table("repair_procedure_action_states")
    op.drop_column("procedure_actions", "skippable")
    op.execute(
        sa.text(
            "REVOKE SELECT ON repair_capability_policies, procedure_actions, "
            "procedure_action_dependencies, procedure_action_requirement_uses, "
            f"procedure_action_evidence FROM {APP_ROLE}"
        )
    )
