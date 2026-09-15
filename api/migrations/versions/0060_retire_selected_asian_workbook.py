"""Retire the orphaned selected-Asian workbook lineage.

The 363-row workbook import was an early breadth proof.  It intentionally kept
all rows unverified because authoritative per-row citations were not retained.
Later provider-backed identity collection superseded this bootstrap data.

This cleanup is deliberately fail-closed: if any workbook configuration has
acquired a real downstream dependency, the migration aborts instead of deleting
that configuration or its dependent data.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0060_retire_workbook"
down_revision: str | None = "0059_primary_vehicle_domains"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORKBOOK_NAME = "Selected_Asian_Brands_1996_2000.xlsx"
SOURCE_COMMIT = "ab954125d89f8ae4cfc42d35af177ec1fe3938a8"
INGESTION_SOURCE_NAME = f"github:{SOURCE_COMMIT}:{WORKBOOK_NAME}"
COVERAGE_BATCH_KEY = "selected-asian-1996-2000-v1"
EXPECTED_TOTAL = 363
EXPECTED_MAKE_COUNTS = {
    "Acura": 62,
    "Honda": 114,
    "Lexus": 18,
    "Subaru": 63,
    "Toyota": 106,
}

# Every current foreign-key path to vehicle_configurations except the legacy
# catalog_coverage_items relationship, which is validated separately below.
PROTECTED_CONFIGURATION_REFERENCES = (
    ("diagnostic_cause_relationships", "vehicle_configuration_id"),
    ("mechanical_claims", "vehicle_configuration_id"),
    ("part_fitments", "vehicle_configuration_id"),
    ("physical_relationships", "vehicle_configuration_id"),
    ("repair_definitions", "vehicle_configuration_id"),
    ("user_vehicles", "canonical_configuration_id"),
    ("vehicle_diagnostic_inspections", "vehicle_configuration_id"),
    ("vehicle_diagnostic_signals", "vehicle_configuration_id"),
    ("vehicle_electrical_applicability", "vehicle_configuration_id"),
    ("vehicle_electrical_connections", "vehicle_configuration_id"),
    ("vehicle_material_applicability", "vehicle_configuration_id"),
    ("vehicle_specification_profiles", "vehicle_configuration_id"),
    ("vehicle_specification_values", "vehicle_configuration_id"),
    ("vehicle_structure_nodes", "vehicle_configuration_id"),
)

WORKBOOK_CONFIGURATION_SQL = """
    SELECT id
    FROM vehicle_configurations
    WHERE identity_source = 'workbook'
      AND verification_status = 'unverified'
      AND market = 'US'
      AND year BETWEEN 1996 AND 2000
"""


def _scalar(bind: sa.Connection, sql: str, params: dict[str, object] | None = None) -> int:
    value = bind.execute(sa.text(sql), params or {}).scalar_one()
    return int(value)


def _assert_workbook_identity_set(bind: sa.Connection) -> None:
    rows = bind.execute(
        sa.text(
            """
            SELECT make, count(*) AS row_count
            FROM vehicle_configurations
            WHERE identity_source = 'workbook'
              AND verification_status = 'unverified'
              AND market = 'US'
              AND year BETWEEN 1996 AND 2000
            GROUP BY make
            ORDER BY make
            """
        )
    ).mappings()
    make_counts = {str(row["make"]): int(row["row_count"]) for row in rows}
    if make_counts != EXPECTED_MAKE_COUNTS:
        raise RuntimeError(
            "Selected-Asian workbook identity set changed unexpectedly: "
            f"expected {EXPECTED_MAKE_COUNTS!r}, found {make_counts!r}"
        )


def _assert_staging_lineage(bind: sa.Connection) -> None:
    batch_count = _scalar(
        bind,
        """
        SELECT count(*)
        FROM catalog_staging.ingestion_batches
        WHERE source_name = :source_name
        """,
        {"source_name": INGESTION_SOURCE_NAME},
    )
    if batch_count != 1:
        raise RuntimeError(
            "Selected-Asian workbook ingestion batch changed unexpectedly: "
            f"expected 1, found {batch_count}"
        )

    source_record_count = _scalar(
        bind,
        """
        SELECT count(*)
        FROM catalog_staging.source_records AS source_record
        JOIN catalog_staging.ingestion_batches AS batch
          ON batch.id = source_record.batch_id
        WHERE batch.source_name = :source_name
          AND source_record.candidate_type = 'vehicle_identity'
          AND source_record.review_status = 'pending'
          AND source_record.extraction_method = 'curated_workbook_import'
        """,
        {"source_name": INGESTION_SOURCE_NAME},
    )
    if source_record_count != EXPECTED_TOTAL:
        raise RuntimeError(
            "Selected-Asian workbook staging lineage changed unexpectedly: "
            f"expected {EXPECTED_TOTAL}, found {source_record_count}"
        )


def _assert_coverage_lineage(bind: sa.Connection) -> None:
    batch_count = _scalar(
        bind,
        "SELECT count(*) FROM catalog_coverage_batches WHERE batch_key = :batch_key",
        {"batch_key": COVERAGE_BATCH_KEY},
    )
    if batch_count != 1:
        raise RuntimeError(
            "Selected-Asian workbook coverage batch changed unexpectedly: "
            f"expected 1, found {batch_count}"
        )

    item_count = _scalar(
        bind,
        """
        SELECT count(*)
        FROM catalog_coverage_items AS item
        JOIN catalog_coverage_batches AS batch ON batch.id = item.batch_id
        WHERE batch.batch_key = :batch_key
          AND item.vehicle_configuration_id IN (
              SELECT id
              FROM vehicle_configurations
              WHERE identity_source = 'workbook'
                AND verification_status = 'unverified'
                AND market = 'US'
                AND year BETWEEN 1996 AND 2000
          )
          AND item.verification_status = 'unverified'
          AND item.source_match_count = 0
        """,
        {"batch_key": COVERAGE_BATCH_KEY},
    )
    if item_count != EXPECTED_TOTAL:
        raise RuntimeError(
            "Selected-Asian workbook coverage items changed unexpectedly: "
            f"expected {EXPECTED_TOTAL}, found {item_count}"
        )

    unrelated_coverage_count = _scalar(
        bind,
        f"""
        SELECT count(*)
        FROM catalog_coverage_items AS item
        JOIN catalog_coverage_batches AS batch ON batch.id = item.batch_id
        WHERE item.vehicle_configuration_id IN ({WORKBOOK_CONFIGURATION_SQL})
          AND batch.batch_key <> :batch_key
        """,
        {"batch_key": COVERAGE_BATCH_KEY},
    )
    if unrelated_coverage_count:
        raise RuntimeError(
            "Selected-Asian workbook configurations are referenced by non-legacy "
            f"coverage data: found {unrelated_coverage_count} rows"
        )


def _assert_no_protected_references(bind: sa.Connection) -> None:
    for table_name, column_name in PROTECTED_CONFIGURATION_REFERENCES:
        count = _scalar(
            bind,
            f"""
            SELECT count(*)
            FROM {table_name}
            WHERE {column_name} IN ({WORKBOOK_CONFIGURATION_SQL})
            """,
        )
        if count:
            raise RuntimeError(
                "Selected-Asian workbook cleanup blocked by downstream data: "
                f"{table_name}.{column_name} has {count} referencing row(s)"
            )


def upgrade() -> None:
    bind = op.get_bind()

    _assert_workbook_identity_set(bind)
    _assert_staging_lineage(bind)
    _assert_coverage_lineage(bind)
    _assert_no_protected_references(bind)

    coverage_delete = bind.execute(
        sa.text("DELETE FROM catalog_coverage_batches WHERE batch_key = :batch_key"),
        {"batch_key": COVERAGE_BATCH_KEY},
    )
    if coverage_delete.rowcount != 1:
        raise RuntimeError(
            "Selected-Asian workbook coverage cleanup did not delete exactly one batch"
        )

    staging_delete = bind.execute(
        sa.text(
            """
            DELETE FROM catalog_staging.ingestion_batches
            WHERE source_name = :source_name
            """
        ),
        {"source_name": INGESTION_SOURCE_NAME},
    )
    if staging_delete.rowcount != 1:
        raise RuntimeError(
            "Selected-Asian workbook staging cleanup did not delete exactly one batch"
        )

    configuration_delete = bind.execute(
        sa.text(
            """
            DELETE FROM vehicle_configurations
            WHERE identity_source = 'workbook'
              AND verification_status = 'unverified'
              AND market = 'US'
              AND year BETWEEN 1996 AND 2000
            """
        )
    )
    if configuration_delete.rowcount != EXPECTED_TOTAL:
        raise RuntimeError(
            "Selected-Asian workbook configuration cleanup changed unexpectedly: "
            f"expected {EXPECTED_TOTAL}, deleted {configuration_delete.rowcount}"
        )


def downgrade() -> None:
    raise RuntimeError(
        "0060_retire_workbook is an intentional data-retirement migration and cannot "
        "be downgraded in place. Restore from a pre-0060 database snapshot if the "
        "retired workbook lineage must be recovered."
    )
