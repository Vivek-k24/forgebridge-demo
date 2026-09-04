"""Add resumable local catalog collection workbench state."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_local_workbench"
down_revision: str | None = "0020_catalog_coverage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "catalog_coverage_items",
        sa.Column(
            "collection_status",
            sa.String(length=24),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )
    op.add_column(
        "catalog_coverage_items",
        sa.Column(
            "source_observation_count",
            sa.SmallInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "catalog_coverage_items",
        sa.Column("last_collected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_catalog_coverage_items_collection_status",
        "catalog_coverage_items",
        "collection_status IN ('pending', 'collecting', 'collected', 'failed')",
    )
    op.create_check_constraint(
        "ck_catalog_coverage_items_source_observation_count",
        "catalog_coverage_items",
        "source_observation_count >= 0",
    )

    op.create_table(
        "catalog_collection_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("make", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("cursor_position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("collected_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verified_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_configuration_id", sa.Uuid(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('queued', 'running', 'paused', 'completed', 'failed', 'cancelled')",
            name="ck_catalog_collection_jobs_status",
        ),
        sa.CheckConstraint(
            "cursor_position >= 0 AND total_items >= 0 AND processed_items >= 0 "
            "AND collected_items >= 0 AND verified_items >= 0",
            name="ck_catalog_collection_jobs_nonnegative_counts",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["catalog_coverage_batches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["last_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_catalog_collection_jobs_batch_make_created",
        "catalog_collection_jobs",
        ["batch_id", "make", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_catalog_collection_jobs_status_created",
        "catalog_collection_jobs",
        ["status", "created_at"],
        unique=False,
    )

    op.create_table(
        "catalog_workbench_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "details",
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
        sa.CheckConstraint(
            "level IN ('info', 'warning', 'error')",
            name="ck_catalog_workbench_logs_level",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["catalog_collection_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_catalog_workbench_logs_job_created",
        "catalog_workbench_logs",
        ["job_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "catalog_workbench_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("fetch_status", sa.String(length=24), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column(
            "matched_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("raw_sha256", sa.String(length=64), nullable=True),
        sa.Column("cache_path", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "fetch_status IN ('success', 'failed', 'blocked', 'not_found')",
            name="ck_catalog_workbench_sources_fetch_status",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["catalog_collection_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id",
            "vehicle_configuration_id",
            "provider",
            name="uq_catalog_workbench_sources_job_vehicle_provider",
        ),
    )
    op.create_index(
        "ix_catalog_workbench_sources_job_created",
        "catalog_workbench_sources",
        ["job_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_catalog_workbench_sources_vehicle",
        "catalog_workbench_sources",
        ["vehicle_configuration_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_catalog_workbench_sources_vehicle",
        table_name="catalog_workbench_sources",
    )
    op.drop_index(
        "ix_catalog_workbench_sources_job_created",
        table_name="catalog_workbench_sources",
    )
    op.drop_table("catalog_workbench_sources")
    op.drop_index(
        "ix_catalog_workbench_logs_job_created",
        table_name="catalog_workbench_logs",
    )
    op.drop_table("catalog_workbench_logs")
    op.drop_index(
        "ix_catalog_collection_jobs_status_created",
        table_name="catalog_collection_jobs",
    )
    op.drop_index(
        "ix_catalog_collection_jobs_batch_make_created",
        table_name="catalog_collection_jobs",
    )
    op.drop_table("catalog_collection_jobs")
    op.drop_constraint(
        "ck_catalog_coverage_items_source_observation_count",
        "catalog_coverage_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_catalog_coverage_items_collection_status",
        "catalog_coverage_items",
        type_="check",
    )
    op.drop_column("catalog_coverage_items", "last_collected_at")
    op.drop_column("catalog_coverage_items", "source_observation_count")
    op.drop_column("catalog_coverage_items", "collection_status")
