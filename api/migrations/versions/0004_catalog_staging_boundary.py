"""Add catalog staging, verified evidence, and collector privilege boundary."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_catalog_staging_boundary"
down_revision: str | None = "0003_vehicle_selection_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAGING_SCHEMA = "catalog_staging"
COLLECTOR_ROLE = "partgraph_collector"


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {STAGING_SCHEMA}"))
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{COLLECTOR_ROLE}') THEN
                    CREATE ROLE {COLLECTOR_ROLE} NOLOGIN;
                END IF;
            END
            $$
            """
        )
    )

    op.create_table(
        "ingestion_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("collector_version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=24), server_default="open", nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('open', 'completed', 'failed')",
            name="ck_catalog_ingestion_batches_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=STAGING_SCHEMA,
    )

    op.create_table(
        "source_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("source_record_id", sa.String(length=256), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("candidate_type", sa.String(length=64), nullable=False),
        sa.Column("raw_sha256", sa.String(length=64), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("candidate_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("vehicle_identity", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("extraction_method", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("review_status", sa.String(length=24), server_default="pending", nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_catalog_source_records_confidence",
        ),
        sa.CheckConstraint(
            "review_status IN ('pending', 'verified', 'rejected')",
            name="ck_catalog_source_records_review_status",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            [f"{STAGING_SCHEMA}.ingestion_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
        schema=STAGING_SCHEMA,
    )
    op.create_index(
        op.f("ix_catalog_staging_source_records_batch_id"),
        "source_records",
        ["batch_id"],
        unique=False,
        schema=STAGING_SCHEMA,
    )

    op.create_table(
        "catalog_verified_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("staging_record_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_type", sa.String(length=64), nullable=False),
        sa.Column("verified_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("vehicle_identity", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_record_id", sa.String(length=256), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("raw_sha256", sa.String(length=64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("extraction_method", sa.String(length=64), nullable=False),
        sa.Column("promoted_by", sa.String(length=128), nullable=False),
        sa.Column(
            "promoted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("staging_record_id"),
    )

    op.execute(sa.text(f"GRANT USAGE ON SCHEMA {STAGING_SCHEMA} TO {COLLECTOR_ROLE}"))
    op.execute(
        sa.text(
            f"GRANT SELECT ON {STAGING_SCHEMA}.ingestion_batches, "
            f"{STAGING_SCHEMA}.source_records TO {COLLECTOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"GRANT INSERT (id, source_name, source_type, collector_version, status) "
            f"ON {STAGING_SCHEMA}.ingestion_batches TO {COLLECTOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"GRANT UPDATE (status, completed_at) ON {STAGING_SCHEMA}.ingestion_batches "
            f"TO {COLLECTOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"GRANT INSERT (id, batch_id, source_record_id, source_url, fetched_at, observed_at, "
            f"candidate_type, raw_sha256, raw_payload, candidate_payload, vehicle_identity, "
            f"provenance, extraction_method, confidence, dedupe_key) "
            f"ON {STAGING_SCHEMA}.source_records TO {COLLECTOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON public.vehicle_configurations "
            f"FROM {COLLECTOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON public.catalog_verified_evidence "
            f"FROM {COLLECTOR_ROLE}"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            f"REVOKE ALL PRIVILEGES ON {STAGING_SCHEMA}.source_records FROM {COLLECTOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"REVOKE ALL PRIVILEGES ON {STAGING_SCHEMA}.ingestion_batches FROM {COLLECTOR_ROLE}"
        )
    )
    op.execute(sa.text(f"REVOKE USAGE ON SCHEMA {STAGING_SCHEMA} FROM {COLLECTOR_ROLE}"))
    op.drop_table("catalog_verified_evidence")
    op.drop_index(
        op.f("ix_catalog_staging_source_records_batch_id"),
        table_name="source_records",
        schema=STAGING_SCHEMA,
    )
    op.drop_table("source_records", schema=STAGING_SCHEMA)
    op.drop_table("ingestion_batches", schema=STAGING_SCHEMA)
    op.execute(sa.text(f"DROP SCHEMA {STAGING_SCHEMA}"))
