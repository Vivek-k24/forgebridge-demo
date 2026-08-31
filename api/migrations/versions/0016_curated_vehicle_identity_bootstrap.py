"""Bootstrap the first reviewed production vehicle identity.

This is a one-record curated data migration, not an automated collector.  The
source is a public NHTSA-hosted Honda Tech Line record used only for vehicle
identity facts within the source's explicit scope.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "0016_vehicle_identity_bootstrap"
down_revision: str | None = "0015_runtime_role_membership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CURATED_AT = datetime(2026, 8, 31, 19, 20, tzinfo=UTC)
REVIEWER = "partgraph-production-bootstrap-2026-08-31"

SOURCE_ID = UUID("76207964-7ee6-5ce3-83ce-cbeb1f8f57a0")
BATCH_ID = UUID("72254767-275d-5ea1-aef1-0ef027423814")
STAGING_RECORD_ID = UUID("c3c779c7-a574-5a96-854b-ff3109ac3f0c")
EVIDENCE_ID = UUID("374a9c0b-058d-5782-8cf9-fd55a935b225")
VEHICLE_ID = UUID("7feb13e9-bca0-5d8b-b701-f0260cce5da1")
CLAIM_ID = UUID("60db9bce-3edf-5e28-94b1-2b34995bc43c")

SOURCE_KEY = "nhtsa-honda-tech-line-dp10004"
SOURCE_NAME = "nhtsa-honda-tech-line-dp10004"
SOURCE_RECORD_ID = "INRD-DP10004-48962P:p390"
SOURCE_URL = "https://static.nhtsa.gov/odi/inv/2010/INRD-DP10004-48962P.pdf"
RAW_SHA256 = "9cb45d72f7558a14dc0bc821151fb1f69e32080cac614861d47c974bb45b6feb"
DEDUPE_KEY = "68b1770a2825328282e688392573146d9b78d8de477a1514dedf453673d49e6e"
BASE_IDENTITY_HASH = "53086d5a08c45bc93113f4a190950290b8109627a1d5ec109239f5abce560e56"
IDENTITY_HASH = "31111f85a4f95ba85abbe452c132c20eddd02e0f7242c088e49f1a328bee45cb"
NORMALIZED_KEY = "vehicle:US:2009:Honda:CIVIC:HYBRID"

RAW_PAYLOAD: dict[str, object] = {
    "document_id": "INRD-DP10004-48962P",
    "document_kind": "NHTSA-hosted Honda Tech Line investigation record",
    "page": 390,
    "vehicle_fields": {
        "year": 2009,
        "model": "CIVIC HYBRID",
        "description": "CIVIC IMA 4DR HYBLNAV 4CYL 110.0",
        "transmission": "CVT",
        "engine_number_prefix": "LDA2",
        "market_marker": "USA",
    },
}

CANDIDATE_PAYLOAD: dict[str, object] = {
    "year": 2009,
    "market": "US",
    "make": "Honda",
    "model": "CIVIC",
    "generation": None,
    "trim": "HYBRID",
    "body_style": None,
    "engine": "I4 HYBRID",
    "transmission": "CVT",
    "drivetrain": None,
}

PROVENANCE: dict[str, object] = {
    "document": {
        "id": "INRD-DP10004-48962P",
        "page": 390,
        "host": "NHTSA",
        "origin": "Honda Tech Line",
    },
    "year": "Dealer / Vehicle Information: Year 2009",
    "market": "Dealer / Vehicle Information: WhtBdy includes USA",
    "make": "Honda Tech Line record and Honda dealer context",
    "model": "ISIS search criteria: MODEL: CIVIC HYBRID",
    "trim": "ISIS search criteria: MODEL: CIVIC HYBRID",
    "engine": "Dealer / Vehicle Information description includes 4CYL; model is CIVIC HYBRID",
    "transmission": "Dealer / Vehicle Information: Tran CVT",
    "excluded_from_canonical_identity": {
        "body_style": "4DR is recorded, but this bootstrap does not infer a body-style label",
        "drivetrain": "not explicitly established by this evidence record",
        "engine_displacement": "not explicitly established by this evidence record",
        "generation": "not explicitly established by this evidence record",
    },
}


def _json(value: dict[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            INSERT INTO catalog_sources (
                id, source_key, display_name, source_class, license_status,
                automation_allowed, terms_url, notes, created_at, updated_at
            ) VALUES (
                :id, :source_key, :display_name, 'government', 'approved',
                FALSE, :terms_url, :notes, :created_at, :created_at
            )
            ON CONFLICT (source_key) DO NOTHING
            """
        ),
        {
            "id": SOURCE_ID,
            "source_key": SOURCE_KEY,
            "display_name": "NHTSA-hosted Honda Tech Line investigation record",
            "terms_url": "https://www.nhtsa.gov/nhtsa-datasets-and-apis",
            "notes": (
                "Public government-hosted record manually reviewed for vehicle identity only. "
                "Automation remains disabled; this source does not establish repair procedure truth."
            ),
            "created_at": CURATED_AT,
        },
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO catalog_staging.ingestion_batches (
                id, source_name, source_type, collector_version, status,
                started_at, completed_at, created_at
            ) VALUES (
                :id, :source_name, 'government', :collector_version, 'completed',
                :curated_at, :curated_at, :curated_at
            )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "id": BATCH_ID,
            "source_name": SOURCE_NAME,
            "collector_version": "manual-curation-1",
            "curated_at": CURATED_AT,
        },
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO catalog_staging.source_records (
                id, batch_id, source_record_id, source_url, fetched_at, observed_at,
                candidate_type, raw_sha256, raw_payload, candidate_payload,
                vehicle_identity, provenance, extraction_method, confidence,
                review_status, reviewed_at, reviewed_by, dedupe_key, created_at
            ) VALUES (
                :id, :batch_id, :source_record_id, :source_url, :curated_at, NULL,
                'vehicle_identity', :raw_sha256, CAST(:raw_payload AS JSONB),
                CAST(:candidate_payload AS JSONB), CAST(:vehicle_identity AS JSONB),
                CAST(:provenance AS JSONB), 'manual_deterministic_extraction', 1.0000,
                'verified', :curated_at, :reviewer, :dedupe_key, :curated_at
            )
            ON CONFLICT (dedupe_key) DO NOTHING
            """
        ),
        {
            "id": STAGING_RECORD_ID,
            "batch_id": BATCH_ID,
            "source_record_id": SOURCE_RECORD_ID,
            "source_url": SOURCE_URL,
            "curated_at": CURATED_AT,
            "raw_sha256": RAW_SHA256,
            "raw_payload": _json(RAW_PAYLOAD),
            "candidate_payload": _json(CANDIDATE_PAYLOAD),
            "vehicle_identity": _json(CANDIDATE_PAYLOAD),
            "provenance": _json(PROVENANCE),
            "reviewer": REVIEWER,
            "dedupe_key": DEDUPE_KEY,
        },
    )

    staging_record_id = bind.execute(
        sa.text(
            "SELECT id FROM catalog_staging.source_records WHERE dedupe_key = :dedupe_key"
        ),
        {"dedupe_key": DEDUPE_KEY},
    ).scalar_one()

    bind.execute(
        sa.text(
            """
            INSERT INTO catalog_verified_evidence (
                id, staging_record_id, candidate_type, verified_payload,
                vehicle_identity, source_name, source_type, source_record_id,
                source_url, raw_sha256, fetched_at, observed_at, provenance,
                extraction_method, promoted_by, promoted_at
            ) VALUES (
                :id, :staging_record_id, 'vehicle_identity',
                CAST(:candidate_payload AS JSONB), CAST(:vehicle_identity AS JSONB),
                :source_name, 'government', :source_record_id, :source_url,
                :raw_sha256, :curated_at, NULL, CAST(:provenance AS JSONB),
                'manual_deterministic_extraction', :reviewer, :curated_at
            )
            ON CONFLICT (staging_record_id) DO NOTHING
            """
        ),
        {
            "id": EVIDENCE_ID,
            "staging_record_id": staging_record_id,
            "candidate_payload": _json(CANDIDATE_PAYLOAD),
            "vehicle_identity": _json(CANDIDATE_PAYLOAD),
            "source_name": SOURCE_NAME,
            "source_record_id": SOURCE_RECORD_ID,
            "source_url": SOURCE_URL,
            "raw_sha256": RAW_SHA256,
            "curated_at": CURATED_AT,
            "provenance": _json(PROVENANCE),
            "reviewer": REVIEWER,
        },
    )

    evidence_id = bind.execute(
        sa.text(
            "SELECT id FROM catalog_verified_evidence WHERE staging_record_id = :staging_record_id"
        ),
        {"staging_record_id": staging_record_id},
    ).scalar_one()

    bind.execute(
        sa.text(
            """
            INSERT INTO vehicle_configurations (
                id, identity_hash, base_identity_hash, canonicalization_version,
                year, market, make, model, generation, trim, body_style, engine,
                transmission, drivetrain, identity_source, verification_status,
                created_at, updated_at
            ) VALUES (
                :id, :identity_hash, :base_identity_hash, 2,
                2009, 'US', 'Honda', 'CIVIC', NULL, 'HYBRID', NULL, 'I4 HYBRID',
                'CVT', NULL, 'nhtsa', 'verified', :curated_at, :curated_at
            )
            ON CONFLICT (identity_hash) DO NOTHING
            """
        ),
        {
            "id": VEHICLE_ID,
            "identity_hash": IDENTITY_HASH,
            "base_identity_hash": BASE_IDENTITY_HASH,
            "curated_at": CURATED_AT,
        },
    )

    vehicle_id = bind.execute(
        sa.text("SELECT id FROM vehicle_configurations WHERE identity_hash = :identity_hash"),
        {"identity_hash": IDENTITY_HASH},
    ).scalar_one()

    bind.execute(
        sa.text(
            """
            UPDATE vehicle_configurations
            SET verification_status = 'verified',
                identity_source = CASE
                    WHEN verification_status = 'verified' THEN identity_source
                    ELSE 'nhtsa'
                END,
                updated_at = :curated_at
            WHERE id = :vehicle_id
            """
        ),
        {"vehicle_id": vehicle_id, "curated_at": CURATED_AT},
    )

    source_id = bind.execute(
        sa.text("SELECT id FROM catalog_sources WHERE source_key = :source_key"),
        {"source_key": SOURCE_KEY},
    ).scalar_one()

    bind.execute(
        sa.text(
            """
            INSERT INTO mechanical_claims (
                id, source_id, verified_evidence_id, vehicle_configuration_id,
                claim_domain, claim_risk, normalized_key, repair_key, claim_payload,
                explicit_claim, exact_applicability, promotion_state, conflict_key,
                superseded_by_id, created_at, reviewed_at, reviewed_by
            ) VALUES (
                :id, :source_id, :evidence_id, :vehicle_id,
                'vehicle_identity', 'normal', :normalized_key, NULL,
                CAST(:claim_payload AS JSONB), TRUE, TRUE, 'verified',
                :conflict_key, NULL, :curated_at, :curated_at, :reviewer
            )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "id": CLAIM_ID,
            "source_id": source_id,
            "evidence_id": evidence_id,
            "vehicle_id": vehicle_id,
            "normalized_key": NORMALIZED_KEY,
            "claim_payload": _json(CANDIDATE_PAYLOAD),
            "conflict_key": "vehicle_identity:US:2009:Honda:CIVIC:HYBRID",
            "curated_at": CURATED_AT,
            "reviewer": REVIEWER,
        },
    )


def downgrade() -> None:
    bind = op.get_bind()

    vehicle_id = bind.execute(
        sa.text(
            "SELECT vehicle_configuration_id FROM mechanical_claims WHERE id = :claim_id"
        ),
        {"claim_id": CLAIM_ID},
    ).scalar_one_or_none()

    bind.execute(sa.text("DELETE FROM mechanical_claims WHERE id = :id"), {"id": CLAIM_ID})
    bind.execute(
        sa.text("DELETE FROM catalog_verified_evidence WHERE id = :id"),
        {"id": EVIDENCE_ID},
    )
    bind.execute(
        sa.text("DELETE FROM catalog_staging.source_records WHERE id = :id"),
        {"id": STAGING_RECORD_ID},
    )
    bind.execute(
        sa.text("DELETE FROM catalog_staging.ingestion_batches WHERE id = :id"),
        {"id": BATCH_ID},
    )
    bind.execute(
        sa.text(
            """
            DELETE FROM catalog_sources
            WHERE id = :id
              AND NOT EXISTS (
                  SELECT 1 FROM mechanical_claims WHERE source_id = :id
              )
            """
        ),
        {"id": SOURCE_ID},
    )

    if vehicle_id is None:
        return

    deleted = bind.execute(
        sa.text(
            """
            DELETE FROM vehicle_configurations
            WHERE id = :vehicle_id
              AND id = :bootstrap_vehicle_id
              AND NOT EXISTS (
                  SELECT 1 FROM user_vehicles
                  WHERE canonical_configuration_id = :vehicle_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM repair_definitions
                  WHERE vehicle_configuration_id = :vehicle_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM mechanical_claims
                  WHERE vehicle_configuration_id = :vehicle_id
              )
            """
        ),
        {"vehicle_id": vehicle_id, "bootstrap_vehicle_id": VEHICLE_ID},
    ).rowcount

    if deleted:
        return

    bind.execute(
        sa.text(
            """
            UPDATE vehicle_configurations
            SET verification_status = 'unverified',
                identity_source = 'manual',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :vehicle_id
              AND identity_source = 'nhtsa'
              AND NOT EXISTS (
                  SELECT 1
                  FROM mechanical_claims
                  WHERE vehicle_configuration_id = :vehicle_id
                    AND claim_domain = 'vehicle_identity'
                    AND promotion_state = 'verified'
              )
            """
        ),
        {"vehicle_id": vehicle_id},
    )
