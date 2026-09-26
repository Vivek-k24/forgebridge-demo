"""Add canonical component and manufacturer part identity schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034_parts_components"
down_revision: str | None = "0033_vehicle_structure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"
SHARED_TABLES = "component_definitions, part_identities, component_part_roles"


def upgrade() -> None:
    op.create_table(
        "component_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("component_key", sa.String(length=160), nullable=False),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("component_key"),
    )

    op.create_table(
        "part_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("manufacturer", sa.String(length=96), nullable=False),
        sa.Column("part_number", sa.String(length=96), nullable=False),
        sa.Column("revision", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "manufacturer",
            "part_number",
            "revision",
            name="uq_part_identities_manufacturer_number_revision",
        ),
    )
    op.create_index(
        "ix_part_identities_part_number",
        "part_identities",
        ["part_number"],
    )

    op.create_table(
        "component_part_roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("component_id", sa.Uuid(), nullable=False),
        sa.Column("part_id", sa.Uuid(), nullable=False),
        sa.Column("position_key", sa.String(length=96), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["component_id"],
            ["component_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["part_id"],
            ["part_identities.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "component_id",
            "part_id",
            "position_key",
            name="uq_component_part_roles_component_part_position",
        ),
    )
    op.create_index(
        "ix_component_part_roles_component_id",
        "component_part_roles",
        ["component_id"],
    )
    op.create_index(
        "ix_component_part_roles_part_id",
        "component_part_roles",
        ["part_id"],
    )

    op.execute(sa.text(f"GRANT SELECT ON {SHARED_TABLES} TO {APP_ROLE}, {REVIEWER_ROLE}"))
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON {SHARED_TABLES} FROM {APP_ROLE}, {REVIEWER_ROLE}"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"REVOKE SELECT ON {SHARED_TABLES} FROM {APP_ROLE}, {REVIEWER_ROLE}"))
    op.drop_index("ix_component_part_roles_part_id", table_name="component_part_roles")
    op.drop_index("ix_component_part_roles_component_id", table_name="component_part_roles")
    op.drop_table("component_part_roles")
    op.drop_index("ix_part_identities_part_number", table_name="part_identities")
    op.drop_table("part_identities")
    op.drop_table("component_definitions")
