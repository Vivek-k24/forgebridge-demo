"""Track collection and verification coverage for canonical vehicle batches."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_catalog_coverage"
down_revision: str | None = "0019_civic_observations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BATCH_KEY = "selected-asian-1996-2000-v1"
BATCH_ID = uuid5(NAMESPACE_URL, f"partgraph:catalog-coverage:{BATCH_KEY}")
SOURCE_COMMIT = "ab954125d89f8ae4cfc42d35af177ec1fe3938a8"
WORKBOOK_NAME = "Selected_Asian_Brands_1996_2000.xlsx"
EXPECTED_TOTAL = 363
EXPECTED_MAKE_COUNTS = {
    "Acura": 62,
    "Honda": 114,
    "Lexus": 18,
    "Subaru": 63,
    "Toyota": 106,
}


def _coverage_item_id(configuration_id: UUID) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"partgraph:catalog-coverage:{BATCH_KEY}:{configuration_id}",
    )


def upgrade() -> None:
    op.create_table(
        "catalog_coverage_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_key", sa.String(length=96), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("target_rows", sa.Integer(), nullable=False),
        sa.Column("verification_rule", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
            "target_rows >= 1",
            name="ck_catalog_coverage_batches_target_rows",
        ),
        sa.CheckConstraint(
            "status IN ('collecting', 'verifying', 'verified', 'superseded')",
            name="ck_catalog_coverage_batches_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_key"),
    )

    op.create_table(
        "catalog_coverage_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("verification_status", sa.String(length=24), nullable=False),
        sa.Column("source_match_count", sa.SmallInteger(), nullable=False),
        sa.Column("source_matrix", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
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
            "source_match_count >= 0",
            name="ck_catalog_coverage_items_source_match_count",
        ),
        sa.CheckConstraint(
            "verification_status IN ('unverified', 'verified', 'conflict')",
            name="ck_catalog_coverage_items_verification_status",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["catalog_coverage_batches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id",
            "vehicle_configuration_id",
            name="uq_catalog_coverage_items_batch_vehicle",
        ),
    )
    op.create_index(
        "ix_catalog_coverage_items_batch_id",
        "catalog_coverage_items",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        "ix_catalog_coverage_items_vehicle_configuration_id",
        "catalog_coverage_items",
        ["vehicle_configuration_id"],
        unique=False,
    )
    op.create_index(
        "ix_catalog_coverage_items_batch_status",
        "catalog_coverage_items",
        ["batch_id", "verification_status"],
        unique=False,
    )

    bind = op.get_bind()
    configurations = list(
        bind.execute(
            sa.text(
                """
                SELECT id, make
                FROM vehicle_configurations
                WHERE identity_source = 'workbook'
                  AND market = 'US'
                  AND year BETWEEN 1996 AND 2000
                ORDER BY make, year, model, trim, engine, transmission, id
                """
            )
        )
    )
    if len(configurations) != EXPECTED_TOTAL:
        raise RuntimeError(
            f"Expected {EXPECTED_TOTAL} workbook configurations, found {len(configurations)}"
        )

    make_counts = Counter(row.make for row in configurations)
    if dict(make_counts) != EXPECTED_MAKE_COUNTS:
        raise RuntimeError(
            "Workbook make coverage changed unexpectedly: "
            f"expected {EXPECTED_MAKE_COUNTS!r}, found {dict(make_counts)!r}"
        )

    batches = sa.table(
        "catalog_coverage_batches",
        sa.column("id", sa.Uuid()),
        sa.column("batch_key", sa.String()),
        sa.column("label", sa.String()),
        sa.column("target_rows", sa.Integer()),
        sa.column("verification_rule", sa.String()),
        sa.column("status", sa.String()),
        sa.column("scope", postgresql.JSONB()),
    )
    op.bulk_insert(
        batches,
        [
            {
                "id": BATCH_ID,
                "batch_key": BATCH_KEY,
                "label": "Selected Asian brands 1996-2000",
                "target_rows": EXPECTED_TOTAL,
                "verification_rule": "three_independent_sources",
                "status": "verifying",
                "scope": {
                    "artifact": WORKBOOK_NAME,
                    "repository_commit": SOURCE_COMMIT,
                    "market": "US",
                    "year_start": 1996,
                    "year_end": 2000,
                    "makes": list(EXPECTED_MAKE_COUNTS),
                    "expected_make_counts": EXPECTED_MAKE_COUNTS,
                },
            }
        ],
    )

    items = sa.table(
        "catalog_coverage_items",
        sa.column("id", sa.Uuid()),
        sa.column("batch_id", sa.Uuid()),
        sa.column("vehicle_configuration_id", sa.Uuid()),
        sa.column("verification_status", sa.String()),
        sa.column("source_match_count", sa.SmallInteger()),
        sa.column("source_matrix", postgresql.JSONB()),
    )
    op.bulk_insert(
        items,
        [
            {
                "id": _coverage_item_id(row.id),
                "batch_id": BATCH_ID,
                "vehicle_configuration_id": row.id,
                "verification_status": "unverified",
                "source_match_count": 0,
                "source_matrix": {
                    "rule": "three_independent_sources",
                    "sources": [],
                    "status": "pending_verification",
                },
            }
            for row in configurations
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_catalog_coverage_items_batch_status", table_name="catalog_coverage_items")
    op.drop_index(
        "ix_catalog_coverage_items_vehicle_configuration_id",
        table_name="catalog_coverage_items",
    )
    op.drop_index("ix_catalog_coverage_items_batch_id", table_name="catalog_coverage_items")
    op.drop_table("catalog_coverage_items")
    op.drop_table("catalog_coverage_batches")
