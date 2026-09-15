"""Retire pre-modern verified specification observations.

The historical reference profile and five curated source transcriptions predate
PartGraph's immutable-evidence publication boundary. The profile remains useful
as historical/reference data, but the curated transcription hashes are not
original-source-byte evidence and therefore must not retain canonical verified
status.

This migration fails closed on any unexpected lineage or downstream evidence
link. Schema-only baseline installations, where the historical reference data
was never loaded, are an intentional no-op.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0061_retire_legacy_specs"
down_revision: str | None = "0060_retire_workbook"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Keep the validation and mutation in PostgreSQL so Alembic offline SQL contains
# the same fail-closed production-cutover guardrails as an online upgrade.
CLEANUP_SQL = r"""
DO $partgraph$
DECLARE
    profile_count bigint;
    batch_count bigint;
    record_count bigint;
    exact_batch_record_count bigint;
    matching_record_count bigint;
    evidence_reference_count bigint;
    matrix_source_count bigint;
    matrix_legacy_source_count bigint;
    updated_count bigint;
    deleted_count bigint;
BEGIN
    SELECT count(*)
      INTO profile_count
      FROM vehicle_specification_profiles
     WHERE id = '48a527db-2d90-52f9-a9da-0aa761718703'::uuid;

    SELECT count(*)
      INTO batch_count
      FROM catalog_staging.ingestion_batches
     WHERE id IN (
        '223e0ca1-00de-525b-adae-3f85f2758a13'::uuid,
        'e37e4db7-35f8-5c39-989c-c68ec679330a'::uuid,
        '1802efef-8132-54e7-9c88-bbcfee0786ff'::uuid,
        'd998778a-7bdc-5eee-8f96-6dfb20d978c1'::uuid,
        '5a29f477-57fd-5456-8793-e1eb76fbbc0e'::uuid
     );

    SELECT count(*)
      INTO record_count
      FROM catalog_staging.source_records
     WHERE id IN (
        '5bda9ae5-4261-5665-8c10-f4c883834f97'::uuid,
        'a4e07213-30b8-5c5f-aab3-0f3749a23c32'::uuid,
        'ba69ed81-a2e4-58f7-97ec-d66b9419a043'::uuid,
        'bfa4a814-d130-5a0e-ad45-a03d08206736'::uuid,
        'd963a269-ac99-5ee5-996b-26561a35cd14'::uuid
     );

    IF profile_count = 0 AND batch_count = 0 AND record_count = 0 THEN
        RETURN;
    END IF;

    IF profile_count <> 1 THEN
        RAISE EXCEPTION
            'Legacy specification cleanup expected one reference profile, found %',
            profile_count;
    END IF;

    IF batch_count <> 5 THEN
        RAISE EXCEPTION
            'Legacy specification cleanup expected five ingestion batches, found %',
            batch_count;
    END IF;

    IF record_count <> 5 THEN
        RAISE EXCEPTION
            'Legacy specification cleanup expected five source records, found %',
            record_count;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM vehicle_specification_profiles
         WHERE id = '48a527db-2d90-52f9-a9da-0aa761718703'::uuid
           AND vehicle_configuration_id = '7feb13e9-bca0-5d8b-b701-f0260cce5da1'::uuid
           AND profile_version = 1
           AND verification_status = 'verified'
           AND source_match_count = 4
           AND jsonb_array_length(source_matrix -> 'sources') = 6
    ) THEN
        RAISE EXCEPTION
            'Legacy specification profile changed unexpectedly; refusing retirement';
    END IF;

    SELECT count(*)
      INTO exact_batch_record_count
      FROM (
        SELECT batch_id
          FROM catalog_staging.source_records
         WHERE batch_id IN (
            '223e0ca1-00de-525b-adae-3f85f2758a13'::uuid,
            'e37e4db7-35f8-5c39-989c-c68ec679330a'::uuid,
            '1802efef-8132-54e7-9c88-bbcfee0786ff'::uuid,
            'd998778a-7bdc-5eee-8f96-6dfb20d978c1'::uuid,
            '5a29f477-57fd-5456-8793-e1eb76fbbc0e'::uuid
         )
         GROUP BY batch_id
        HAVING count(*) = 1
      ) AS one_record_batches;

    IF exact_batch_record_count <> 5 THEN
        RAISE EXCEPTION
            'Legacy specification ingestion batches no longer contain exactly one record each';
    END IF;

    SELECT count(*)
      INTO matching_record_count
      FROM catalog_staging.source_records
     WHERE (id, batch_id) IN (
        ('5bda9ae5-4261-5665-8c10-f4c883834f97'::uuid, '223e0ca1-00de-525b-adae-3f85f2758a13'::uuid),
        ('a4e07213-30b8-5c5f-aab3-0f3749a23c32'::uuid, 'e37e4db7-35f8-5c39-989c-c68ec679330a'::uuid),
        ('ba69ed81-a2e4-58f7-97ec-d66b9419a043'::uuid, '1802efef-8132-54e7-9c88-bbcfee0786ff'::uuid),
        ('bfa4a814-d130-5a0e-ad45-a03d08206736'::uuid, 'd998778a-7bdc-5eee-8f96-6dfb20d978c1'::uuid),
        ('d963a269-ac99-5ee5-996b-26561a35cd14'::uuid, '5a29f477-57fd-5456-8793-e1eb76fbbc0e'::uuid)
     )
       AND candidate_type = 'vehicle_specification_candidate'
       AND review_status = 'verified'
       AND extraction_method = 'curated_transcription'
       AND vehicle_identity ->> 'vehicle_configuration_id' =
           '7feb13e9-bca0-5d8b-b701-f0260cce5da1'
       AND provenance ->> 'capture_kind' = 'curated_transcription';

    IF matching_record_count <> 5 THEN
        RAISE EXCEPTION
            'Legacy specification source-record semantics changed unexpectedly';
    END IF;

    SELECT count(*)
      INTO evidence_reference_count
      FROM catalog_verified_evidence
     WHERE staging_record_id IN (
        '5bda9ae5-4261-5665-8c10-f4c883834f97'::uuid,
        'a4e07213-30b8-5c5f-aab3-0f3749a23c32'::uuid,
        'ba69ed81-a2e4-58f7-97ec-d66b9419a043'::uuid,
        'bfa4a814-d130-5a0e-ad45-a03d08206736'::uuid,
        'd963a269-ac99-5ee5-996b-26561a35cd14'::uuid
     );

    IF evidence_reference_count <> 0 THEN
        RAISE EXCEPTION
            'Legacy specification cleanup blocked by % immutable-evidence reference(s)',
            evidence_reference_count;
    END IF;

    SELECT jsonb_array_length(source_matrix -> 'sources')
      INTO matrix_source_count
      FROM vehicle_specification_profiles
     WHERE id = '48a527db-2d90-52f9-a9da-0aa761718703'::uuid;

    SELECT count(*)
      INTO matrix_legacy_source_count
      FROM vehicle_specification_profiles AS profile,
           LATERAL jsonb_array_elements(profile.source_matrix -> 'sources') AS source_entry
     WHERE profile.id = '48a527db-2d90-52f9-a9da-0aa761718703'::uuid
       AND source_entry ->> 'id' IN (
          'cars_2009_civic_hybrid',
          'honda_2009_hybrid_owner_manual',
          'kbb_2009_civic_hybrid',
          'edmunds_2009_civic_hybrid',
          'honda_2009_hybrid_fact_sheet'
       );

    IF matrix_source_count <> 6 OR matrix_legacy_source_count <> 5 THEN
        RAISE EXCEPTION
            'Legacy specification profile source matrix changed unexpectedly';
    END IF;

    UPDATE vehicle_specification_profiles
       SET verification_status = 'candidate',
           source_matrix = jsonb_set(
               source_matrix,
               '{governance}',
               jsonb_build_object(
                   'status', 'legacy_candidate',
                   'reason',
                   concat(
                       'Pre-modern curated transcriptions are retained for historical reference ',
                       'but do not satisfy the immutable-evidence publication boundary.'
                   ),
                   'remediated_revision', '0061_retire_legacy_specs'
               ),
               true
           ),
           updated_at = now()
     WHERE id = '48a527db-2d90-52f9-a9da-0aa761718703'::uuid
       AND verification_status = 'verified';
    GET DIAGNOSTICS updated_count = ROW_COUNT;

    IF updated_count <> 1 THEN
        RAISE EXCEPTION
            'Legacy specification cleanup expected one profile downgrade, found %',
            updated_count;
    END IF;

    DELETE FROM catalog_staging.ingestion_batches
     WHERE id IN (
        '223e0ca1-00de-525b-adae-3f85f2758a13'::uuid,
        'e37e4db7-35f8-5c39-989c-c68ec679330a'::uuid,
        '1802efef-8132-54e7-9c88-bbcfee0786ff'::uuid,
        'd998778a-7bdc-5eee-8f96-6dfb20d978c1'::uuid,
        '5a29f477-57fd-5456-8793-e1eb76fbbc0e'::uuid
     );
    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    IF deleted_count <> 5 THEN
        RAISE EXCEPTION
            'Legacy specification cleanup expected five batch deletions, found %',
            deleted_count;
    END IF;
END
$partgraph$;
"""


def upgrade() -> None:
    op.execute(sa.text(CLEANUP_SQL))


def downgrade() -> None:
    raise RuntimeError(
        "0061_retire_legacy_specs is an intentional provenance correction and data "
        "retirement migration. Restore from a pre-0061 snapshot to recover the "
        "retired staging lineage or verified legacy profile state."
    )
