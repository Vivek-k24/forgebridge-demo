import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import CatalogIngestionBatch, CatalogSourceRecord, CatalogVerifiedEvidence


class CatalogStagingError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StageRecordInput:
    source_record_id: str
    source_url: str
    fetched_at: datetime
    candidate_type: str
    raw_payload: dict[str, object]
    candidate_payload: dict[str, object]
    provenance: dict[str, object]
    extraction_method: str
    observed_at: datetime | None = None
    vehicle_identity: dict[str, object] | None = None
    confidence: float | None = None


def _required(value: str, field: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise CatalogStagingError(f"{field} is required")
    return normalized


def _payload_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dedupe_key(source_name: str, source_record_id: str, raw_sha256: str) -> str:
    identity = "\x1f".join((source_name.casefold(), source_record_id.casefold(), raw_sha256))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


async def create_ingestion_batch(
    session: AsyncSession,
    *,
    source_name: str,
    source_type: str,
    collector_version: str | None = None,
) -> CatalogIngestionBatch:
    batch = CatalogIngestionBatch(
        source_name=_required(source_name, "source_name"),
        source_type=_required(source_type, "source_type"),
        collector_version=(" ".join(collector_version.split()) if collector_version else None),
        status="open",
    )
    session.add(batch)
    await session.flush()
    return batch


async def stage_source_record(
    session: AsyncSession,
    *,
    batch_id: UUID,
    record: StageRecordInput,
) -> tuple[CatalogSourceRecord, bool]:
    batch = await session.get(CatalogIngestionBatch, batch_id)
    if batch is None:
        raise CatalogStagingError("ingestion batch does not exist")
    if batch.status != "open":
        raise CatalogStagingError("ingestion batch is not open")

    source_record_id = _required(record.source_record_id, "source_record_id")
    source_url = _required(record.source_url, "source_url")
    candidate_type = _required(record.candidate_type, "candidate_type")
    extraction_method = _required(record.extraction_method, "extraction_method")
    if record.confidence is not None and not 0 <= record.confidence <= 1:
        raise CatalogStagingError("confidence must be between 0 and 1")

    raw_sha256 = _payload_hash(record.raw_payload)
    dedupe_key = _dedupe_key(batch.source_name, source_record_id, raw_sha256)
    new_id = uuid4()
    statement = (
        insert(CatalogSourceRecord)
        .values(
            id=new_id,
            batch_id=batch_id,
            source_record_id=source_record_id,
            source_url=source_url,
            fetched_at=record.fetched_at,
            observed_at=record.observed_at,
            candidate_type=candidate_type,
            raw_sha256=raw_sha256,
            raw_payload=record.raw_payload,
            candidate_payload=record.candidate_payload,
            vehicle_identity=record.vehicle_identity,
            provenance=record.provenance,
            extraction_method=extraction_method,
            confidence=(Decimal(str(record.confidence)) if record.confidence is not None else None),
            dedupe_key=dedupe_key,
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
        .returning(CatalogSourceRecord.id)
    )
    inserted_id = (await session.execute(statement)).scalar_one_or_none()
    resolved_id = inserted_id or (
        await session.execute(
            select(CatalogSourceRecord.id).where(CatalogSourceRecord.dedupe_key == dedupe_key)
        )
    ).scalar_one()
    staged = await session.get(CatalogSourceRecord, resolved_id)
    if staged is None:
        raise RuntimeError("staged catalog record disappeared after insert")
    return staged, inserted_id is not None


async def complete_ingestion_batch(
    session: AsyncSession,
    batch_id: UUID,
    *,
    failed: bool = False,
) -> CatalogIngestionBatch:
    batch = await session.get(CatalogIngestionBatch, batch_id)
    if batch is None:
        raise CatalogStagingError("ingestion batch does not exist")
    if batch.status != "open":
        return batch
    batch.status = "failed" if failed else "completed"
    batch.completed_at = datetime.now(UTC)
    await session.flush()
    return batch


async def promote_verified_record(
    session: AsyncSession,
    *,
    record_id: UUID,
    reviewer: str,
) -> tuple[CatalogVerifiedEvidence, bool]:
    reviewer = _required(reviewer, "reviewer")
    record = (
        await session.execute(
            select(CatalogSourceRecord)
            .where(CatalogSourceRecord.id == record_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if record is None:
        raise CatalogStagingError("staging record does not exist")
    if record.review_status == "rejected":
        raise CatalogStagingError("rejected staging evidence cannot be promoted")

    existing = (
        await session.execute(
            select(CatalogVerifiedEvidence).where(
                CatalogVerifiedEvidence.staging_record_id == record.id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    batch = await session.get(CatalogIngestionBatch, record.batch_id)
    if batch is None:
        raise RuntimeError("staging record has no ingestion batch")

    evidence = CatalogVerifiedEvidence(
        staging_record_id=record.id,
        candidate_type=record.candidate_type,
        verified_payload=record.candidate_payload,
        vehicle_identity=record.vehicle_identity,
        source_name=batch.source_name,
        source_type=batch.source_type,
        source_record_id=record.source_record_id,
        source_url=record.source_url,
        raw_sha256=record.raw_sha256,
        fetched_at=record.fetched_at,
        observed_at=record.observed_at,
        provenance=record.provenance,
        extraction_method=record.extraction_method,
        promoted_by=reviewer,
    )
    record.review_status = "verified"
    record.reviewed_at = datetime.now(UTC)
    record.reviewed_by = reviewer
    session.add(evidence)
    await session.flush()
    return evidence, True


async def reject_staging_record(
    session: AsyncSession,
    *,
    record_id: UUID,
    reviewer: str,
) -> CatalogSourceRecord:
    reviewer = _required(reviewer, "reviewer")
    record = (
        await session.execute(
            select(CatalogSourceRecord)
            .where(CatalogSourceRecord.id == record_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if record is None:
        raise CatalogStagingError("staging record does not exist")
    if record.review_status == "verified":
        raise CatalogStagingError("verified evidence cannot be rejected in place")
    record.review_status = "rejected"
    record.reviewed_at = datetime.now(UTC)
    record.reviewed_by = reviewer
    await session.flush()
    return record
