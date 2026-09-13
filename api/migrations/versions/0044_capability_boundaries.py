"""Add canonical safety and capability procedure boundaries."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0044_capability_boundaries"
down_revision: str | None = "0043_electrical"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"
SHARED_TABLES = (
    "capability_boundary_definitions, repair_capability_boundaries, "
    "procedure_action_capability_boundaries"
)


def upgrade() -> None:
    op.create_table(
        "capability_boundary_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("boundary_key", sa.String(length=120), nullable=False),
        sa.Column("boundary_kind", sa.String(length=32), nullable=False),
        sa.Column("guidance_state", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("rationale", sa.String(length=500), nullable=False),
        sa.Column("user_message", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "boundary_kind IN ('computer_service_tool', 'high_voltage_internal', "
            "'specialized_procedure', 'professional_only', 'other')",
            name="ck_capability_boundary_definitions_kind",
        ),
        sa.CheckConstraint(
            "guidance_state IN ('information_only', 'professional_required', "
            "'prohibited', 'unsupported_indefinitely')",
            name="ck_capability_boundary_definitions_state",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("boundary_key"),
    )
    op.create_index(
        "ix_capability_boundary_definitions_kind",
        "capability_boundary_definitions",
        ["boundary_kind"],
    )
    op.create_index(
        "ix_capability_boundary_definitions_state",
        "capability_boundary_definitions",
        ["guidance_state"],
    )

    op.create_table(
        "repair_capability_boundaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repair_definition_id", sa.Uuid(), nullable=False),
        sa.Column("boundary_definition_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["repair_definition_id"],
            ["repair_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["boundary_definition_id"],
            ["capability_boundary_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repair_definition_id",
            "boundary_definition_id",
            name="uq_repair_capability_boundaries_definition",
        ),
    )
    op.create_index(
        "ix_repair_capability_boundaries_repair",
        "repair_capability_boundaries",
        ["repair_definition_id"],
    )

    op.create_table(
        "procedure_action_capability_boundaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("boundary_definition_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["action_id"],
            ["procedure_actions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["boundary_definition_id"],
            ["capability_boundary_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "action_id",
            name="uq_procedure_action_capability_boundaries_action",
        ),
    )

    op.execute(sa.text(f"GRANT SELECT ON {SHARED_TABLES} TO {APP_ROLE}, {REVIEWER_ROLE}"))
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON {SHARED_TABLES} FROM {APP_ROLE}, {REVIEWER_ROLE}"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"REVOKE SELECT ON {SHARED_TABLES} FROM {APP_ROLE}, {REVIEWER_ROLE}"))
    op.drop_table("procedure_action_capability_boundaries")
    op.drop_index(
        "ix_repair_capability_boundaries_repair",
        table_name="repair_capability_boundaries",
    )
    op.drop_table("repair_capability_boundaries")
    op.drop_index(
        "ix_capability_boundary_definitions_state",
        table_name="capability_boundary_definitions",
    )
    op.drop_index(
        "ix_capability_boundary_definitions_kind",
        table_name="capability_boundary_definitions",
    )
    op.drop_table("capability_boundary_definitions")
