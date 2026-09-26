"""Add part supersession, service replacement and interchange relationships."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036_part_interchange"
down_revision: str | None = "0035_part_fitment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"


def upgrade() -> None:
    op.create_table(
        "part_relationships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_part_id", sa.Uuid(), nullable=False),
        sa.Column("target_part_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "relationship_type IN ('supersedes', 'service_replacement', 'interchange')",
            name="ck_part_relationships_type",
        ),
        sa.CheckConstraint(
            "source_part_id <> target_part_id",
            name="ck_part_relationships_distinct_parts",
        ),
        sa.ForeignKeyConstraint(
            ["source_part_id"],
            ["part_identities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_part_id"],
            ["part_identities.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_part_id",
            "target_part_id",
            "relationship_type",
            name="uq_part_relationships_edge",
        ),
    )
    op.create_index(
        "ix_part_relationships_source_part_id",
        "part_relationships",
        ["source_part_id"],
    )
    op.create_index(
        "ix_part_relationships_target_type",
        "part_relationships",
        ["target_part_id", "relationship_type"],
    )

    op.execute(sa.text(f"GRANT SELECT ON part_relationships TO {APP_ROLE}, {REVIEWER_ROLE}"))
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON part_relationships FROM {APP_ROLE}, {REVIEWER_ROLE}"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"REVOKE SELECT ON part_relationships FROM {APP_ROLE}, {REVIEWER_ROLE}"))
    op.drop_index("ix_part_relationships_target_type", table_name="part_relationships")
    op.drop_index("ix_part_relationships_source_part_id", table_name="part_relationships")
    op.drop_table("part_relationships")
