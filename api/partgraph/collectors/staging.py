"""Generic collector boundary for raw catalog observations.

Collectors write only to ``catalog_staging``. They never promote a vehicle,
part, fitment claim, or inventory offer directly into canonical truth.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..knowledge.models import CatalogIngestionBatch, CatalogSourceRecord


class CandidateType(StrEnum):
    VEHICLE_TRIM = "vehicle_trim_candidate"
    PART = "part_candidate"
    PART_FITMENT = "part_fitment_candidate"
    INVENTORY_OFFER = "inventory_offer_candidate"
    SOURCE_DOCUMENT = "source_document_candidate"


@dataclass(frozen=True, slots=True)
class StageResult:
    record: CatalogSourceRecord
    inserted: bool


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def raw_payload_sha256(payload: dict[str, Any]) -> str:
    return sha256(canonical_json_bytes(payload)).hexdigest()


def observation_dedupe_key(
    *, source_name: str, source_record_id: str, raw_sha256: str
) -> str:
    material = f"{source_name}\0{source_record_id}\0{raw_sha256}".encode()
    return sha256(material).hexdigest()


async def start_ingestion_batch(
    session: AsyncSession,
    *,
    source_name: str,
    source_type: str,
    collector_version: str,
) -> CatalogIngestionBatch:
    batch = CatalogIngestionBatch(
        source_name=source_name,
        source_type=source_type,
        collector_version=collector_version,
        status="open",
    )
    session.add(batch)
    await session.flush()
    return batch


async def finish_ingestion_batch(
    session: AsyncSession,
    batch: CatalogIngestionBatch,
    *,
    status: str = "completed",
) -> None:
    if status not in {"completed", "failed"}:
        raise ValueError("batch completion status must be 'completed' or 'failed'")
    batch.status = status
    batch.completed_at = datetime.now(UTC)
    await session.flush()


async def stage_observation(
    session: AsyncSession,
    *,
    batch: CatalogIngestionBatch,
    source_record_id: str,
    source_url: str,
    candidate_type: CandidateType | str,
    raw_payload: dict[str, Any],
    candidate_payload: dict[str, Any],
    provenance: dict[str, Any],
    extraction_method: str,
    vehicle_identity: dict[str, Any] | None = None,
    confidence: float | Decimal | None = None,
    observed_at: datetime | None = None,
    fetched_at: datetime | None = None,
) -> StageResult:
    """Persist one immutable raw observation and its extracted candidate.

    The dedupe key includes the raw checksum. A listing or source record may
    therefore be observed again when its price, availability, fitment, or
    other source payload changes without overwriting prior evidence. An
    unchanged observation is idempotently reused instead of failing the batch.
    """

    raw_hash = raw_payload_sha256(raw_payload)
    dedupe_key = observation_dedupe_key(
        source_name=batch.source_name,
        source_record_id=source_record_id,
        raw_sha256=raw_hash,
    )
    existing = await session.scalar(
        select(CatalogSourceRecord).where(CatalogSourceRecord.dedupe_key == dedupe_key)
    )
    if existing is not None:
        return StageResult(record=existing, inserted=False)

    record = CatalogSourceRecord(
        batch_id=batch.id,
        source_record_id=source_record_id,
        source_url=source_url,
        fetched_at=fetched_at or datetime.now(UTC),
        observed_at=observed_at,
        candidate_type=str(candidate_type),
        raw_sha256=raw_hash,
        raw_payload=raw_payload,
        candidate_payload=candidate_payload,
        vehicle_identity=vehicle_identity,
        provenance=provenance,
        extraction_method=extraction_method,
        confidence=Decimal(str(confidence)) if confidence is not None else None,
        review_status="pending",
        dedupe_key=dedupe_key,
    )
    session.add(record)
    await session.flush()
    return StageResult(record=record, inserted=True)
