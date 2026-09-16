"""Add exact-configuration part fitment and applicability schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0035_part_fitment"
down_revision: str | None = "0034_parts_components"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"


def upgrade() -> None:
    op.create_table(
        "part_fitments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("component_part_role_id", sa.Uuid(), nullable=False),
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
            name="ck_part_fitments_state",
        ),
        sa.CheckConstraint(
            "applicability_state <> 'conditional' OR qualifier_key <> ''",
            name="ck_part_fitments_conditional_key",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["component_part_role_id"],
            ["component_part_roles.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "vehicle_configuration_id",
            "component_part_role_id",
            "qualifier_key",
            name="uq_part_fitments_vehicle_role_qualifier",
        ),
    )
    op.create_index(
        "ix_part_fitments_vehicle_configuration_id",
        "part_fitments",
        ["vehicle_configuration_id"],
    )
    op.create_index(
        "ix_part_fitments_component_part_role_id",
        "part_fitments",
        ["component_part_role_id"],
    )
    op.create_index(
        "ix_part_fitments_vehicle_state",
        "part_fitments",
        ["vehicle_configuration_id", "applicability_state"],
    )

    op.execute(sa.text(f"GRANT SELECT ON part_fitments TO {APP_ROLE}, {REVIEWER_ROLE}"))
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON part_fitments FROM {APP_ROLE}, {REVIEWER_ROLE}"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"REVOKE SELECT ON part_fitments FROM {APP_ROLE}, {REVIEWER_ROLE}"))
    op.drop_index("ix_part_fitments_vehicle_state", table_name="part_fitments")
    op.drop_index("ix_part_fitments_component_part_role_id", table_name="part_fitments")
    op.drop_index("ix_part_fitments_vehicle_configuration_id", table_name="part_fitments")
    op.drop_table("part_fitments")
