"""Seed reviewed 2009 Civic Hybrid field observations for reconciliation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_civic_observations"
down_revision: str | None = "0018_civic_hybrid_profile"
branch_labels = None
depends_on = None

VEHICLE_ID = UUID("7feb13e9-bca0-5d8b-b701-f0260cce5da1")
CAPTURED_AT = datetime(2026, 9, 3, tzinfo=UTC)

SOURCES = {
    "honda_2009_hybrid_fact_sheet": {
        "source_type": "manufacturer",
        "source_class": "manufacturer",
        "url": (
            "https://automobiles.honda.com/images/2009/civic-hybrid/downloads/"
            "2009-civic-hybrid-factsheet.pdf"
        ),
        "fields": {
            "identity.trim": "HYBRID",
            "identity.body_style": "Sedan",
            "identity.drivetrain": "FWD",
            "identity.transmission": "CVT",
            "powertrain.engine": "1.3L I4 HYBRID",
            "powertrain.displacement_cc": 1339,
            "powertrain.combined_horsepower_hp": 110,
            "powertrain.combined_torque_lb_ft": 123,
            "efficiency.epa_city_mpg": 40,
            "efficiency.epa_highway_mpg": 45,
            "efficiency.epa_combined_mpg": 42,
            "efficiency.fuel_tank_gallons": 12.3,
            "dimensions_weight.wheelbase_in": 106.3,
            "dimensions_weight.length_in": 177.3,
            "dimensions_weight.curb_weight_lb": 2877,
            "chassis.front_suspension": "MacPherson strut",
            "chassis.rear_suspension": "Multi-link",
            "chassis.tires": "P195/65 R15 89S",
        },
    },
    "edmunds_2009_civic_hybrid": {
        "source_type": "vehicle_reference",
        "source_class": "vehicle_reference",
        "url": (
            "https://www.edmunds.com/honda/civic/2009/sedan/st-101061181/"
            "features-specs/"
        ),
        "fields": {
            "identity.trim": "HYBRID",
            "identity.body_style": "Sedan",
            "identity.drivetrain": "FWD",
            "identity.transmission": "CVT",
            "powertrain.engine": "1.3L I4 HYBRID",
            "powertrain.displacement_cc": 1339,
            "powertrain.combined_horsepower_hp": 110,
            "powertrain.combined_torque_lb_ft": 123,
            "efficiency.epa_city_mpg": 40,
            "efficiency.epa_highway_mpg": 45,
            "efficiency.epa_combined_mpg": 42,
            "efficiency.fuel_tank_gallons": 12.3,
            "dimensions_weight.wheelbase_in": 106.3,
            "dimensions_weight.length_in": 177.3,
            "dimensions_weight.curb_weight_lb": 2877,
            "chassis.front_suspension": "MacPherson strut",
            "chassis.rear_suspension": "Multi-link",
            "chassis.tires": "P195/65 R15 89S",
        },
    },
    "kbb_2009_civic_hybrid": {
        "source_type": "vehicle_reference",
        "source_class": "vehicle_reference",
        "url": "https://www.kbb.com/honda/civic/2009/hybrid-sedan-4d/",
        "fields": {
            "identity.trim": "HYBRID",
            "identity.body_style": "Sedan",
            "identity.drivetrain": "FWD",
            "identity.transmission": "CVT",
            "powertrain.engine": "1.3L I4 HYBRID",
            "powertrain.displacement_cc": 1339,
            "powertrain.combined_horsepower_hp": 110,
            "powertrain.combined_torque_lb_ft": 123,
            "efficiency.epa_city_mpg": 40,
            "efficiency.epa_highway_mpg": 45,
            "efficiency.epa_combined_mpg": 42,
            "efficiency.fuel_tank_gallons": 12.3,
            "dimensions_weight.wheelbase_in": 106.3,
            "dimensions_weight.length_in": 177.3,
            "dimensions_weight.curb_weight_lb": 2877,
        },
    },
    "cars_2009_civic_hybrid": {
        "source_type": "vehicle_reference",
        "source_class": "vehicle_reference",
        "url": "https://www.cars.com/research/honda-civic_hybrid-2009/specs/",
        "fields": {
            "identity.trim": "HYBRID",
            "identity.body_style": "Sedan",
            "identity.drivetrain": "FWD",
            "identity.transmission": "CVT",
            "powertrain.engine": "1.3L I4 HYBRID",
            "powertrain.displacement_cc": 1339,
            "powertrain.combined_horsepower_hp": 110,
            "powertrain.combined_torque_lb_ft": 123,
            "efficiency.epa_city_mpg": 40,
            "efficiency.epa_highway_mpg": 45,
            "efficiency.epa_combined_mpg": 42,
            "efficiency.fuel_tank_gallons": 12.3,
            "dimensions_weight.length_in": 177.0,
            "chassis.front_suspension": "MacPherson strut",
            "chassis.rear_suspension": "Multi-link",
            "chassis.tires": "P195/65 R15 89S",
        },
    },
    "honda_2009_hybrid_owner_manual": {
        "source_type": "manufacturer",
        "source_class": "manufacturer",
        "url": "https://techinfo.honda.com/rjanisis/pubs/OM/NC0909/NC0909OM.pdf",
        "fields": {
            "dimensions_weight.length_in": 176.7,
            "manufacturer_service_specifications.engine_oil_change_with_filter_us_qt": {
                "value": 3.4,
                "kind": "manufacturer_reported",
            },
            "manufacturer_service_specifications.transmission_fluid_change_us_qt": {
                "value": 3.0,
                "kind": "manufacturer_reported",
            },
        },
    },
}


def _id(label: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"partgraph:2009-civic-hybrid:{label}")


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _candidate_fields(raw_fields: dict[str, object]) -> dict[str, dict[str, object]]:
    candidate: dict[str, dict[str, object]] = {}
    for field, raw_value in raw_fields.items():
        if isinstance(raw_value, dict) and "value" in raw_value:
            candidate[field] = {
                "value": raw_value["value"],
                "kind": raw_value.get("kind", "ordinary"),
            }
        else:
            candidate[field] = {"value": raw_value, "kind": "ordinary"}
    return candidate


def upgrade() -> None:
    batches = sa.table(
        "ingestion_batches",
        sa.column("id", sa.Uuid()),
        sa.column("source_name", sa.String()),
        sa.column("source_type", sa.String()),
        sa.column("collector_version", sa.String()),
        sa.column("status", sa.String()),
        sa.column("completed_at", sa.DateTime(timezone=True)),
        schema="catalog_staging",
    )
    records = sa.table(
        "source_records",
        sa.column("id", sa.Uuid()),
        sa.column("batch_id", sa.Uuid()),
        sa.column("source_record_id", sa.String()),
        sa.column("source_url", sa.Text()),
        sa.column("fetched_at", sa.DateTime(timezone=True)),
        sa.column("observed_at", sa.DateTime(timezone=True)),
        sa.column("candidate_type", sa.String()),
        sa.column("raw_sha256", sa.String()),
        sa.column("raw_payload", postgresql.JSONB()),
        sa.column("candidate_payload", postgresql.JSONB()),
        sa.column("vehicle_identity", postgresql.JSONB()),
        sa.column("provenance", postgresql.JSONB()),
        sa.column("extraction_method", sa.String()),
        sa.column("confidence", sa.Numeric()),
        sa.column("review_status", sa.String()),
        sa.column("reviewed_at", sa.DateTime(timezone=True)),
        sa.column("reviewed_by", sa.String()),
        sa.column("dedupe_key", sa.String()),
        schema="catalog_staging",
    )

    batch_rows = []
    record_rows = []
    for source_name, source in SOURCES.items():
        batch_id = _id(f"batch:{source_name}")
        record_id = _id(f"record:{source_name}")
        source_record_id = f"2009-civic-hybrid:{source_name}:profile-v1"
        raw_payload = {
            "capture_kind": "curated_transcription",
            "fields": source["fields"],
        }
        raw_hash = sha256(_canonical_bytes(raw_payload)).hexdigest()
        dedupe_material = f"{source_name}\0{source_record_id}\0{raw_hash}".encode()

        batch_rows.append(
            {
                "id": batch_id,
                "source_name": source_name,
                "source_type": source["source_type"],
                "collector_version": "reference-profile-v1",
                "status": "completed",
                "completed_at": CAPTURED_AT,
            }
        )
        record_rows.append(
            {
                "id": record_id,
                "batch_id": batch_id,
                "source_record_id": source_record_id,
                "source_url": source["url"],
                "fetched_at": CAPTURED_AT,
                "observed_at": None,
                "candidate_type": "vehicle_specification_candidate",
                "raw_sha256": raw_hash,
                "raw_payload": raw_payload,
                "candidate_payload": {"fields": _candidate_fields(source["fields"])},
                "vehicle_identity": {
                    "vehicle_configuration_id": str(VEHICLE_ID),
                    "year": 2009,
                    "market": "US",
                    "make": "Honda",
                    "model": "CIVIC",
                    "trim": "HYBRID",
                },
                "provenance": {
                    "source_class": source["source_class"],
                    "capture_kind": "curated_transcription",
                    "review_boundary": (
                        "Reviewed reference-vehicle observations; original source URLs "
                        "remain authoritative for provenance."
                    ),
                },
                "extraction_method": "curated_transcription",
                "confidence": None,
                "review_status": "verified",
                "reviewed_at": CAPTURED_AT,
                "reviewed_by": "partgraph_reference_profile",
                "dedupe_key": sha256(dedupe_material).hexdigest(),
            }
        )

    op.bulk_insert(batches, batch_rows)
    op.bulk_insert(records, record_rows)


def downgrade() -> None:
    batches = sa.table(
        "ingestion_batches",
        sa.column("id", sa.Uuid()),
        schema="catalog_staging",
    )
    batch_ids = [_id(f"batch:{source_name}") for source_name in SOURCES]
    op.execute(batches.delete().where(batches.c.id.in_(batch_ids)))
