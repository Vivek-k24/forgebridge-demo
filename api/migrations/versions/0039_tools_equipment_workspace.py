"""Add canonical tools, equipment, and workspace requirement resources."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0039_tools_equipment_workspace"
down_revision: str | None = "0038_hardware_fasteners"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"
SHARED_TABLES = (
    "tool_equipment_definitions, workspace_definitions, "
    "tool_equipment_requirement_bindings, workspace_requirement_bindings"
)


def upgrade() -> None:
    op.create_table(
        "tool_equipment_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resource_key", sa.String(length=160), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column(
            "specifications",
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
            "resource_type IN ('hand_tool', 'power_tool', 'specialty_tool', "
            "'lifting_support', 'measuring_diagnostic', 'fluid_service', "
            "'safety_equipment', 'shop_equipment', 'professional_equipment', 'other')",
            name="ck_tool_equipment_definitions_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resource_key"),
    )
    op.create_index(
        "ix_tool_equipment_definitions_resource_type",
        "tool_equipment_definitions",
        ["resource_type"],
    )

    op.create_table(
        "workspace_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_key", sa.String(length=160), nullable=False),
        sa.Column("workspace_type", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column(
            "specifications",
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
            "workspace_type IN ('surface', 'clearance', 'ventilation', 'lighting', "
            "'weather_protection', 'lifting_access', 'fluid_containment', 'power_supply', "
            "'compressed_air', 'fire_safety', 'cleanliness', 'other')",
            name="ck_workspace_definitions_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_key"),
    )
    op.create_index(
        "ix_workspace_definitions_workspace_type",
        "workspace_definitions",
        ["workspace_type"],
    )

    op.create_table(
        "tool_equipment_requirement_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requirement_definition_id", sa.Uuid(), nullable=False),
        sa.Column("tool_equipment_definition_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["requirement_definition_id"],
            ["requirement_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tool_equipment_definition_id"],
            ["tool_equipment_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "requirement_definition_id",
            name="uq_tool_req_bindings_requirement",
        ),
    )
    op.create_index(
        "ix_tool_req_bindings_tool_id",
        "tool_equipment_requirement_bindings",
        ["tool_equipment_definition_id"],
    )

    op.create_table(
        "workspace_requirement_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requirement_definition_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_definition_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["requirement_definition_id"],
            ["requirement_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_definition_id"],
            ["workspace_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "requirement_definition_id",
            name="uq_workspace_req_bindings_requirement",
        ),
    )
    op.create_index(
        "ix_workspace_req_bindings_workspace_id",
        "workspace_requirement_bindings",
        ["workspace_definition_id"],
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
        "ix_workspace_req_bindings_workspace_id",
        table_name="workspace_requirement_bindings",
    )
    op.drop_table("workspace_requirement_bindings")
    op.drop_index(
        "ix_tool_req_bindings_tool_id",
        table_name="tool_equipment_requirement_bindings",
    )
    op.drop_table("tool_equipment_requirement_bindings")
    op.drop_index(
        "ix_workspace_definitions_workspace_type",
        table_name="workspace_definitions",
    )
    op.drop_table("workspace_definitions")
    op.drop_index(
        "ix_tool_equipment_definitions_resource_type",
        table_name="tool_equipment_definitions",
    )
    op.drop_table("tool_equipment_definitions")
