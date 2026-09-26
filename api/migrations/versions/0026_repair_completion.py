"""Add repair completion milestones and downstream requirement state."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_repair_completion"
down_revision: str | None = "0025_preview_bootstrap"
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
        "procedure_action_milestones",
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("milestone_type", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "milestone_type IN ('physical_replacement')",
            name="ck_procedure_action_milestones_type",
        ),
        sa.ForeignKeyConstraint(
            ["action_id"], ["procedure_actions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("action_id"),
    )

    op.create_table(
        "repair_downstream_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_repair_definition_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_key", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("trigger_type", sa.String(length=24), nullable=False),
        sa.Column("trigger_action_id", sa.Uuid(), nullable=True),
        sa.Column("support_state", sa.String(length=32), nullable=False),
        sa.Column("target_repair_definition_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "trigger_type IN ('action_completed', 'procedure_complete')",
            name="ck_repair_downstream_requirements_trigger_type",
        ),
        sa.CheckConstraint(
            "support_state IN ('supported', 'professional_required', 'unsupported')",
            name="ck_repair_downstream_requirements_support_state",
        ),
        sa.CheckConstraint(
            "(trigger_type = 'action_completed' AND trigger_action_id IS NOT NULL) OR "
            "(trigger_type = 'procedure_complete' AND trigger_action_id IS NULL)",
            name="ck_repair_downstream_requirements_trigger_scope",
        ),
        sa.CheckConstraint(
            "(support_state = 'supported' AND target_repair_definition_id IS NOT NULL) OR "
            "(support_state IN ('professional_required', 'unsupported') "
            "AND target_repair_definition_id IS NULL)",
            name="ck_repair_downstream_requirements_target_scope",
        ),
        sa.CheckConstraint(
            "target_repair_definition_id IS NULL OR "
            "target_repair_definition_id <> source_repair_definition_id",
            name="ck_repair_downstream_requirements_not_self",
        ),
        sa.CheckConstraint(
            "position >= 0",
            name="ck_repair_downstream_requirements_position",
        ),
        sa.ForeignKeyConstraint(
            ["source_repair_definition_id"],
            ["repair_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trigger_action_id"],
            ["procedure_actions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_repair_definition_id"],
            ["repair_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_repair_definition_id",
            "requirement_key",
            name="uq_repair_downstream_requirements_definition_key",
        ),
        sa.UniqueConstraint(
            "source_repair_definition_id",
            "position",
            name="uq_repair_downstream_requirements_definition_position",
        ),
    )
    op.create_index(
        "ix_repair_downstream_requirements_source",
        "repair_downstream_requirements",
        ["source_repair_definition_id", "position"],
    )

    op.create_table(
        "repair_downstream_requirement_evidence",
        sa.Column("downstream_requirement_id", sa.Uuid(), nullable=False),
        sa.Column("mechanical_claim_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["downstream_requirement_id"],
            ["repair_downstream_requirements.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["mechanical_claim_id"],
            ["mechanical_claims.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("downstream_requirement_id", "mechanical_claim_id"),
    )

    op.create_table(
        "repair_downstream_requirement_states",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("downstream_requirement_id", sa.Uuid(), nullable=False),
        sa.Column(
            "state",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("resolution_kind", sa.String(length=32), nullable=True),
        sa.Column("resolution_session_id", sa.Uuid(), nullable=True),
        sa.Column("resolution_note", sa.String(length=500), nullable=True),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("satisfied_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('pending', 'satisfied')",
            name="ck_repair_downstream_requirement_states_state",
        ),
        sa.CheckConstraint(
            "resolution_kind IS NULL OR resolution_kind IN "
            "('linked_session_complete', 'external_service_confirmed')",
            name="ck_repair_downstream_requirement_states_resolution_kind",
        ),
        sa.CheckConstraint(
            "(state = 'pending' AND resolution_kind IS NULL AND satisfied_at IS NULL) OR "
            "(state = 'satisfied' AND resolution_kind IS NOT NULL AND satisfied_at IS NOT NULL)",
            name="ck_repair_downstream_requirement_states_resolution",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["repair_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["downstream_requirement_id"],
            ["repair_downstream_requirements.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resolution_session_id"], ["repair_sessions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "session_id", "downstream_requirement_id"
        ),
    )
    op.create_index(
        "ix_repair_downstream_requirement_states_owner_session",
        "repair_downstream_requirement_states",
        ["user_id", "session_id", "state"],
    )

    op.execute(
        sa.text(
            "GRANT SELECT ON procedure_action_milestones, "
            "repair_downstream_requirements, repair_downstream_requirement_evidence "
            f"TO {APP_ROLE}"
        )
    )
    op.execute(
        sa.text(
            "GRANT SELECT, INSERT, UPDATE ON repair_downstream_requirement_states "
            f"TO {APP_ROLE}"
        )
    )
    _owner_policy("repair_downstream_requirement_states")

    op.execute(
        sa.text(
            """
            CREATE FUNCTION partgraph_activate_downstream_requirements()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                source_definition_id uuid;
            BEGIN
                SELECT repair_definition_id
                  INTO source_definition_id
                  FROM repair_sessions
                 WHERE id = NEW.session_id;

                IF source_definition_id IS NULL THEN
                    RETURN NEW;
                END IF;

                IF NEW.progress_state = 'completed' THEN
                    INSERT INTO repair_downstream_requirement_states (
                        user_id,
                        session_id,
                        downstream_requirement_id,
                        state
                    )
                    SELECT
                        NEW.user_id,
                        NEW.session_id,
                        requirement.id,
                        'pending'
                    FROM repair_downstream_requirements AS requirement
                    WHERE requirement.source_repair_definition_id = source_definition_id
                      AND requirement.trigger_type = 'action_completed'
                      AND requirement.trigger_action_id = NEW.action_id
                    ON CONFLICT DO NOTHING;
                END IF;

                IF NEW.progress_state IN ('completed', 'skipped')
                   AND NOT EXISTS (
                        SELECT 1
                        FROM procedure_actions AS action
                        WHERE action.repair_definition_id = source_definition_id
                          AND NOT EXISTS (
                              SELECT 1
                              FROM repair_procedure_action_states AS action_state
                              WHERE action_state.user_id = NEW.user_id
                                AND action_state.session_id = NEW.session_id
                                AND action_state.action_id = action.id
                                AND action_state.progress_state IN ('completed', 'skipped')
                          )
                   ) THEN
                    INSERT INTO repair_downstream_requirement_states (
                        user_id,
                        session_id,
                        downstream_requirement_id,
                        state
                    )
                    SELECT
                        NEW.user_id,
                        NEW.session_id,
                        requirement.id,
                        'pending'
                    FROM repair_downstream_requirements AS requirement
                    WHERE requirement.source_repair_definition_id = source_definition_id
                      AND requirement.trigger_type = 'procedure_complete'
                    ON CONFLICT DO NOTHING;
                END IF;

                RETURN NEW;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_repair_action_activate_downstream
            AFTER INSERT OR UPDATE OF progress_state
            ON repair_procedure_action_states
            FOR EACH ROW
            EXECUTE FUNCTION partgraph_activate_downstream_requirements()
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_repair_action_activate_downstream "
            "ON repair_procedure_action_states"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS partgraph_activate_downstream_requirements()"))
    op.execute(
        sa.text(
            "DROP POLICY IF EXISTS repair_downstream_requirement_states_owner "
            "ON repair_downstream_requirement_states"
        )
    )
    op.drop_index(
        "ix_repair_downstream_requirement_states_owner_session",
        table_name="repair_downstream_requirement_states",
    )
    op.drop_table("repair_downstream_requirement_states")
    op.drop_table("repair_downstream_requirement_evidence")
    op.drop_index(
        "ix_repair_downstream_requirements_source",
        table_name="repair_downstream_requirements",
    )
    op.drop_table("repair_downstream_requirements")
    op.drop_table("procedure_action_milestones")
