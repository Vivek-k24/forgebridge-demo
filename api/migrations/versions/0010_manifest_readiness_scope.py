"""Scope private repair readiness to aggregated manifest requirements."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_manifest_readiness_scope"
down_revision: str | None = "0009_repair_definition_readiness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "repair_requirement_states",
        sa.Column("requirement_definition_id", sa.Uuid(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE repair_requirement_states AS state
            SET requirement_definition_id = requirement_use.requirement_definition_id
            FROM requirement_uses AS requirement_use
            WHERE requirement_use.id = state.requirement_use_id
            """
        )
    )
    op.alter_column(
        "repair_requirement_states",
        "requirement_definition_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_repair_requirement_states_requirement_definition",
        "repair_requirement_states",
        "requirement_definitions",
        ["requirement_definition_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "uq_repair_requirement_states_session_requirement",
        "repair_requirement_states",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_repair_requirement_states_session_requirement_definition",
        "repair_requirement_states",
        ["user_id", "session_id", "requirement_definition_id"],
    )

    op.drop_constraint(
        "repair_requirement_states_requirement_use_id_fkey",
        "repair_requirement_states",
        type_="foreignkey",
    )
    op.drop_column("repair_requirement_states", "requirement_use_id")


def downgrade() -> None:
    op.add_column(
        "repair_requirement_states",
        sa.Column("requirement_use_id", sa.Uuid(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE repair_requirement_states AS state
            SET requirement_use_id = (
                SELECT requirement_use.id
                FROM requirement_uses AS requirement_use
                JOIN repair_sessions AS repair_session
                  ON repair_session.id = state.session_id
                WHERE requirement_use.repair_definition_id = repair_session.repair_definition_id
                  AND requirement_use.requirement_definition_id = state.requirement_definition_id
                ORDER BY requirement_use.id
                LIMIT 1
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM repair_requirement_states
                    WHERE requirement_use_id IS NULL
                ) THEN
                    RAISE EXCEPTION
                        'cannot downgrade manifest readiness: requirement use mapping is missing';
                END IF;
            END
            $$;
            """
        )
    )
    op.alter_column(
        "repair_requirement_states",
        "requirement_use_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_foreign_key(
        "repair_requirement_states_requirement_use_id_fkey",
        "repair_requirement_states",
        "requirement_uses",
        ["requirement_use_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "uq_repair_requirement_states_session_requirement_definition",
        "repair_requirement_states",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_repair_requirement_states_session_requirement",
        "repair_requirement_states",
        ["user_id", "session_id", "requirement_use_id"],
    )

    op.drop_constraint(
        "fk_repair_requirement_states_requirement_definition",
        "repair_requirement_states",
        type_="foreignkey",
    )
    op.drop_column("repair_requirement_states", "requirement_definition_id")
