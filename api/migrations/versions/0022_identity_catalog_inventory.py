"""Add source-backed US make/model/trim inventory tables."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_identity_catalog"
down_revision: str | None = "0021_local_workbench"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalog_identity_models",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("market", sa.String(length=16), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("make", sa.String(length=64), nullable=False),
        sa.Column("make_key", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("model_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("source_count", sa.SmallInteger(), nullable=False),
        sa.Column(
            "sources",
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "year >= 1996 AND year <= 2100",
            name="ck_catalog_identity_models_year",
        ),
        sa.CheckConstraint(
            "status IN ('discovered', 'corroborated')",
            name="ck_catalog_identity_models_status",
        ),
        sa.CheckConstraint(
            "source_count >= 1",
            name="ck_catalog_identity_models_source_count",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "market",
            "year",
            "make_key",
            "model_key",
            name="uq_catalog_identity_models_selection",
        ),
    )
    op.create_index(
        "ix_catalog_identity_models_selection",
        "catalog_identity_models",
        ["market", "year", "make", "model"],
        unique=False,
    )

    op.create_table(
        "catalog_identity_trims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.Uuid(), nullable=False),
        sa.Column("trim", sa.String(length=160), nullable=False),
        sa.Column("trim_key", sa.String(length=192), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("source_count", sa.SmallInteger(), nullable=False),
        sa.Column(
            "sources",
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('discovered', 'corroborated')",
            name="ck_catalog_identity_trims_status",
        ),
        sa.CheckConstraint(
            "source_count >= 1",
            name="ck_catalog_identity_trims_source_count",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["catalog_identity_models.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "model_id",
            "trim_key",
            name="uq_catalog_identity_trims_model_trim",
        ),
    )
    op.create_index(
        "ix_catalog_identity_trims_model",
        "catalog_identity_trims",
        ["model_id", "trim"],
        unique=False,
    )

    op.create_table(
        "catalog_identity_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("make", sa.String(length=64), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("models_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trims_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "source_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_catalog_identity_progress_status",
        ),
        sa.CheckConstraint(
            "models_found >= 0 AND trims_found >= 0",
            name="ck_catalog_identity_progress_counts",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "make",
            "year",
            name="uq_catalog_identity_progress_make_year",
        ),
    )
    op.create_index(
        "ix_catalog_identity_progress_status",
        "catalog_identity_progress",
        ["status", "make", "year"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_catalog_identity_progress_status",
        table_name="catalog_identity_progress",
    )
    op.drop_table("catalog_identity_progress")
    op.drop_index(
        "ix_catalog_identity_trims_model",
        table_name="catalog_identity_trims",
    )
    op.drop_table("catalog_identity_trims")
    op.drop_index(
        "ix_catalog_identity_models_selection",
        table_name="catalog_identity_models",
    )
    op.drop_table("catalog_identity_models")
