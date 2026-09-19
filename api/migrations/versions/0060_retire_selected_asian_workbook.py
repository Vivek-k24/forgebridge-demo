"""Retire the orphaned selected-Asian workbook lineage.

The 363-row workbook import was an early breadth proof. It intentionally kept
all rows unverified because authoritative per-row citations were not retained.
Later provider-backed identity collection superseded this bootstrap data.

This cleanup is deliberately fail-closed: if any workbook configuration has
acquired a real downstream dependency, the migration aborts instead of deleting
that configuration or its dependent data. Schema-only baseline installations,
where the historical lineage was never loaded, are an intentional no-op.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0060_retire_workbook"
down_revision: str | None = "0059_primary_vehicle_domains"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Keep all validation in PostgreSQL so the exact same fail-closed guardrails are
# preserved in Alembic offline SQL used for production cutover review.
CLEANUP_SQL = r"""
DO $partgraph$
DECLARE
    configuration_count bigint;
    ingestion_batch_count bigint;
    source_record_count bigint;
    matching_source_record_count bigint;
    coverage_batch_count bigint;
    coverage_item_count bigint;
    matching_coverage_item_count bigint;
    unrelated_coverage_count bigint;
    protected_reference_count bigint;
    deleted_count bigint;
BEGIN
    SELECT count(*)
      INTO configuration_count
      FROM vehicle_configurations
     WHERE identity_source = 'workbook'
       AND verification_status = 'unverified'
       AND market = 'US'
       AND year BETWEEN 1996 AND 2000;

    SELECT count(*)
      INTO ingestion_batch_count
      FROM catalog_staging.ingestion_batches
     WHERE id = '924c6c9c-150b-5a19-9e00-718313e49193'::uuid;

    SELECT count(*)
      INTO source_record_count
      FROM catalog_staging.source_records
     WHERE batch_id = '924c6c9c-150b-5a19-9e00-718313e49193'::uuid;

    SELECT count(*)
      INTO coverage_batch_count
      FROM catalog_coverage_batches
     WHERE batch_key = 'selected-asian-1996-2000-v1';

    SELECT count(*)
      INTO coverage_item_count
      FROM catalog_coverage_items AS item
      JOIN catalog_coverage_batches AS batch ON batch.id = item.batch_id
     WHERE batch.batch_key = 'selected-asian-1996-2000-v1';

    IF configuration_count = 0
       AND ingestion_batch_count = 0
       AND source_record_count = 0
       AND coverage_batch_count = 0
       AND coverage_item_count = 0 THEN
        RETURN;
    END IF;

    IF configuration_count <> 363 THEN
        RAISE EXCEPTION
            'Selected-Asian workbook identity set changed unexpectedly: expected 363, found %',
            configuration_count;
    END IF;

    IF (SELECT count(*) FROM vehicle_configurations
         WHERE identity_source = 'workbook'
           AND verification_status = 'unverified'
           AND market = 'US'
           AND year BETWEEN 1996 AND 2000
           AND make = 'Acura') <> 62
       OR (SELECT count(*) FROM vehicle_configurations
         WHERE identity_source = 'workbook'
           AND verification_status = 'unverified'
           AND market = 'US'
           AND year BETWEEN 1996 AND 2000
           AND make = 'Honda') <> 114
       OR (SELECT count(*) FROM vehicle_configurations
         WHERE identity_source = 'workbook'
           AND verification_status = 'unverified'
           AND market = 'US'
           AND year BETWEEN 1996 AND 2000
           AND make = 'Lexus') <> 18
       OR (SELECT count(*) FROM vehicle_configurations
         WHERE identity_source = 'workbook'
           AND verification_status = 'unverified'
           AND market = 'US'
           AND year BETWEEN 1996 AND 2000
           AND make = 'Subaru') <> 63
       OR (SELECT count(*) FROM vehicle_configurations
         WHERE identity_source = 'workbook'
           AND verification_status = 'unverified'
           AND market = 'US'
           AND year BETWEEN 1996 AND 2000
           AND make = 'Toyota') <> 106 THEN
        RAISE EXCEPTION 'Selected-Asian workbook make distribution changed unexpectedly';
    END IF;

    IF ingestion_batch_count <> 1 THEN
        RAISE EXCEPTION
            'Selected-Asian workbook ingestion batch changed unexpectedly: expected 1, found %',
            ingestion_batch_count;
    END IF;

    IF source_record_count <> 363 THEN
        RAISE EXCEPTION
            'Selected-Asian workbook staging lineage changed unexpectedly: expected 363, found %',
            source_record_count;
    END IF;

    SELECT count(*)
      INTO matching_source_record_count
      FROM catalog_staging.source_records
     WHERE batch_id = '924c6c9c-150b-5a19-9e00-718313e49193'::uuid
       AND candidate_type = 'vehicle_identity'
       AND review_status = 'pending'
       AND extraction_method = 'curated_workbook_import';

    IF matching_source_record_count <> 363 THEN
        RAISE EXCEPTION
            'Selected-Asian workbook staging records changed semantics: expected 363, found %',
            matching_source_record_count;
    END IF;

    IF coverage_batch_count <> 1 THEN
        RAISE EXCEPTION
            'Selected-Asian workbook coverage batch changed unexpectedly: expected 1, found %',
            coverage_batch_count;
    END IF;

    IF coverage_item_count <> 363 THEN
        RAISE EXCEPTION
            'Selected-Asian workbook coverage lineage changed unexpectedly: expected 363, found %',
            coverage_item_count;
    END IF;

    SELECT count(*)
      INTO matching_coverage_item_count
      FROM catalog_coverage_items AS item
      JOIN catalog_coverage_batches AS batch ON batch.id = item.batch_id
     WHERE batch.batch_key = 'selected-asian-1996-2000-v1'
       AND item.vehicle_configuration_id IN (
           SELECT id
             FROM vehicle_configurations
            WHERE identity_source = 'workbook'
              AND verification_status = 'unverified'
              AND market = 'US'
              AND year BETWEEN 1996 AND 2000
       )
       AND item.verification_status = 'unverified'
       AND item.source_match_count = 0;

    IF matching_coverage_item_count <> 363 THEN
        RAISE EXCEPTION
            'Selected-Asian workbook coverage rows changed semantics: expected 363, found %',
            matching_coverage_item_count;
    END IF;

    SELECT count(*)
      INTO unrelated_coverage_count
      FROM catalog_coverage_items AS item
      JOIN catalog_coverage_batches AS batch ON batch.id = item.batch_id
     WHERE item.vehicle_configuration_id IN (
           SELECT id
             FROM vehicle_configurations
            WHERE identity_source = 'workbook'
              AND verification_status = 'unverified'
              AND market = 'US'
              AND year BETWEEN 1996 AND 2000
       )
       AND batch.batch_key <> 'selected-asian-1996-2000-v1';

    IF unrelated_coverage_count <> 0 THEN
        RAISE EXCEPTION
            'Selected-Asian workbook configurations have % non-legacy coverage reference(s)',
            unrelated_coverage_count;
    END IF;

    SELECT
        (SELECT count(*) FROM diagnostic_cause_relationships
          WHERE vehicle_configuration_id IN (
              SELECT id FROM vehicle_configurations
               WHERE identity_source = 'workbook'
                 AND verification_status = 'unverified'
                 AND market = 'US'
                 AND year BETWEEN 1996 AND 2000))
      + (SELECT count(*) FROM mechanical_claims
          WHERE vehicle_configuration_id IN (
              SELECT id FROM vehicle_configurations
               WHERE identity_source = 'workbook'
                 AND verification_status = 'unverified'
                 AND market = 'US'
                 AND year BETWEEN 1996 AND 2000))
      + (SELECT count(*) FROM part_fitments
          WHERE vehicle_configuration_id IN (
              SELECT id FROM vehicle_configurations
               WHERE identity_source = 'workbook'
                 AND verification_status = 'unverified'
                 AND market = 'US'
                 AND year BETWEEN 1996 AND 2000))
      + (SELECT count(*) FROM physical_relationships
          WHERE vehicle_configuration_id IN (
              SELECT id FROM vehicle_configurations
               WHERE identity_source = 'workbook'
                 AND verification_status = 'unverified'
                 AND market = 'US'
                 AND year BETWEEN 1996 AND 2000))
      + (SELECT count(*) FROM repair_definitions
          WHERE vehicle_configuration_id IN (
              SELECT id FROM vehicle_configurations
               WHERE identity_source = 'workbook'
                 AND verification_status = 'unverified'
                 AND market = 'US'
                 AND year BETWEEN 1996 AND 2000))
      + (SELECT count(*) FROM user_vehicles
          WHERE canonical_configuration_id IN (
              SELECT id FROM vehicle_configurations
               WHERE identity_source = 'workbook'
                 AND verification_status = 'unverified'
                 AND market = 'US'
                 AND year BETWEEN 1996 AND 2000))
      + (SELECT count(*) FROM vehicle_diagnostic_inspections
          WHERE vehicle_configuration_id IN (
              SELECT id FROM vehicle_configurations
               WHERE identity_source = 'workbook'
                 AND verification_status = 'unverified'
                 AND market = 'US'
                 AND year BETWEEN 1996 AND 2000))
      + (SELECT count(*) FROM vehicle_diagnostic_signals
          WHERE vehicle_configuration_id IN (
              SELECT id FROM vehicle_configurations
               WHERE identity_source = 'workbook'
                 AND verification_status = 'unverified'
                 AND market = 'US'
                 AND year BETWEEN 1996 AND 2000))
      + (SELECT count(*) FROM vehicle_electrical_applicability
          WHERE vehicle_configuration_id IN (
              SELECT id FROM vehicle_configurations
               WHERE identity_source = 'workbook'
                 AND verification_status = 'unverified'
                 AND market = 'US'
                 AND year BETWEEN 1996 AND 2000))
      + (SELECT count(*) FROM vehicle_electrical_connections
          WHERE vehicle_configuration_id IN (
              SELECT id FROM vehicle_configurations
               WHERE identity_source = 'workbook'
                 AND verification_status = 'unverified'
                 AND market = 'US'
                 AND year BETWEEN 1996 AND 2000))
      + (SELECT count(*) FROM vehicle_material_applicability
          WHERE vehicle_configuration_id IN (
              SELECT id FROM vehicle_configurations
               WHERE identity_source = 'workbook'
                 AND verification_status = 'unverified'
                 AND market = 'US'
                 AND year BETWEEN 1996 AND 2000))
      + (SELECT count(*) FROM vehicle_specification_profiles
          WHERE vehicle_configuration_id IN (
              SELECT id FROM vehicle_configurations
               WHERE identity_source = 'workbook'
                 AND verification_status = 'unverified'
                 AND market = 'US'
                 AND year BETWEEN 1996 AND 2000))
      + (SELECT count(*) FROM vehicle_specification_values
          WHERE vehicle_configuration_id IN (
              SELECT id FROM vehicle_configurations
               WHERE identity_source = 'workbook'
                 AND verification_status = 'unverified'
                 AND market = 'US'
                 AND year BETWEEN 1996 AND 2000))
      + (SELECT count(*) FROM vehicle_structure_nodes
          WHERE vehicle_configuration_id IN (
              SELECT id FROM vehicle_configurations
               WHERE identity_source = 'workbook'
                 AND verification_status = 'unverified'
                 AND market = 'US'
                 AND year BETWEEN 1996 AND 2000))
      INTO protected_reference_count;

    IF protected_reference_count <> 0 THEN
        RAISE EXCEPTION
            'Selected-Asian workbook cleanup blocked by % downstream reference(s)',
            protected_reference_count;
    END IF;

    DELETE FROM catalog_coverage_batches
     WHERE batch_key = 'selected-asian-1996-2000-v1';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    IF deleted_count <> 1 THEN
        RAISE EXCEPTION
            'Selected-Asian workbook coverage cleanup expected 1 batch deletion, found %',
            deleted_count;
    END IF;

    DELETE FROM catalog_staging.ingestion_batches
     WHERE id = '924c6c9c-150b-5a19-9e00-718313e49193'::uuid;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    IF deleted_count <> 1 THEN
        RAISE EXCEPTION
            'Selected-Asian workbook staging cleanup expected 1 batch deletion, found %',
            deleted_count;
    END IF;

    DELETE FROM vehicle_configurations
     WHERE identity_source = 'workbook'
       AND verification_status = 'unverified'
       AND market = 'US'
       AND year BETWEEN 1996 AND 2000;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    IF deleted_count <> 363 THEN
        RAISE EXCEPTION
            'Selected-Asian workbook cleanup expected 363 configuration deletions, found %',
            deleted_count;
    END IF;
END
$partgraph$;
"""


def upgrade() -> None:
    op.execute(sa.text(CLEANUP_SQL))


def downgrade() -> None:
    raise RuntimeError(
        "0060_retire_workbook is an intentional data-retirement migration and cannot "
        "be downgraded in place. Restore from a pre-0060 database snapshot if the "
        "retired workbook lineage must be recovered."
    )
