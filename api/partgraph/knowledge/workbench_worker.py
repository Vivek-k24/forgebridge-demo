from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import engine, session_factory
from ..identity.vehicle.models import VehicleConfiguration
from .coverage_models import CatalogCoverageItem
from .models import CatalogIngestionBatch, CatalogSourceRecord, CatalogVerifiedEvidence
from .workbench_models import (
    CatalogCollectionJob,
    CatalogWorkbenchLog,
    CatalogWorkbenchSource,
)
from .workbench_sources import SourceFetchResult, fetch_source, source_requests

COLLECTOR_VERSION = "local-workbench-v1"
VERIFIER = "partgraph_local_workbench_three_source_v1"
STALE_JOB_SECONDS = 60
PROVIDERS = ("nhtsa_vpic", "cars_com", "edmunds", "kbb", "motortrend")


def _now() -> datetime:
    return datetime.now(UTC)


def _stable_id(label: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"partgraph:local-workbench:{label}")


async def _log(
    session: AsyncSession,
    job_id: UUID,
    event_type: str,
    message: str,
    *,
    level: str = "info",
    details: dict[str, object] | None = None,
) -> None:
    session.add(
        CatalogWorkbenchLog(
            job_id=job_id,
            level=level,
            event_type=event_type,
            message=message,
            details=details or {},
        )
    )


async def _recover_interrupted_jobs() -> int:
    cutoff = _now() - timedelta(seconds=STALE_JOB_SECONDS)
    recovered = 0
    async with session_factory() as session:
        async with session.begin():
            jobs = list(
                await session.scalars(
                    select(CatalogCollectionJob)
                    .where(
                        CatalogCollectionJob.status == "running",
                        or_(
                            CatalogCollectionJob.last_heartbeat_at.is_(None),
                            CatalogCollectionJob.last_heartbeat_at < cutoff,
                        ),
                    )
                    .with_for_update(skip_locked=True)
                )
            )
            for job in jobs:
                job.status = "queued"
                job.last_error = None
                await _log(
                    session,
                    job.id,
                    "job_recovered",
                    (
                        f"Recovered interrupted {job.make} job at candidate "
                        f"{job.cursor_position + 1}."
                    ),
                    level="warning",
                    details={"cursor_position": job.cursor_position},
                )
                recovered += 1
    return recovered


async def _claim_next_job() -> UUID | None:
    async with session_factory() as session:
        async with session.begin():
            job = await session.scalar(
                select(CatalogCollectionJob)
                .where(CatalogCollectionJob.status == "queued")
                .order_by(CatalogCollectionJob.created_at)
                .with_for_update(skip_locked=True)
            )
            if job is None:
                return None
            now = _now()
            job.status = "running"
            job.started_at = job.started_at or now
            job.last_heartbeat_at = now
            job.last_error = None
            await _log(
                session,
                job.id,
                "job_started",
                f"Started collection for {job.make}.",
                details={"cursor_position": job.cursor_position, "total_items": job.total_items},
            )
            return job.id


async def _job_status(job_id: UUID) -> str | None:
    async with session_factory() as session:
        return await session.scalar(
            select(CatalogCollectionJob.status).where(CatalogCollectionJob.id == job_id)
        )


async def _ensure_ingestion_batch(
    session: AsyncSession,
    job: CatalogCollectionJob,
    provider: str,
) -> CatalogIngestionBatch:
    batch_id = _stable_id(f"ingestion:{job.id}:{provider}")
    item = await session.get(CatalogIngestionBatch, batch_id)
    if item is not None:
        return item
    source_type = "government" if provider == "nhtsa_vpic" else "vehicle_reference"
    item = CatalogIngestionBatch(
        id=batch_id,
        source_name=f"local_workbench_{provider}",
        source_type=source_type,
        collector_version=COLLECTOR_VERSION,
        status="open",
    )
    session.add(item)
    await session.flush()
    return item


def _identity(configuration: VehicleConfiguration) -> dict[str, object]:
    return {
        "vehicle_configuration_id": str(configuration.id),
        "year": configuration.year,
        "market": configuration.market,
        "make": configuration.make,
        "model": configuration.model,
        "trim": configuration.trim,
        "engine": configuration.engine,
        "transmission": configuration.transmission,
        "drivetrain": configuration.drivetrain,
    }


async def _stage_successful_source(
    session: AsyncSession,
    job: CatalogCollectionJob,
    configuration: VehicleConfiguration,
    result: SourceFetchResult,
) -> CatalogSourceRecord:
    assert result.raw_sha256 is not None
    ingestion_batch = await _ensure_ingestion_batch(session, job, result.provider)
    dedupe_key = sha256(
        (
            f"{result.provider}\0{configuration.id}\0{result.source_url}\0"
            f"{result.raw_sha256}"
        ).encode()
    ).hexdigest()
    existing = await session.scalar(
        select(CatalogSourceRecord).where(CatalogSourceRecord.dedupe_key == dedupe_key)
    )
    if existing is not None:
        return existing

    now = _now()
    identity = _identity(configuration)
    record = CatalogSourceRecord(
        batch_id=ingestion_batch.id,
        source_record_id=(
            f"workbench:{result.provider}:{configuration.id}:{result.raw_sha256[:12]}"
        ),
        source_url=result.source_url,
        fetched_at=now,
        observed_at=None,
        candidate_type="vehicle_configuration_reference",
        raw_sha256=result.raw_sha256,
        raw_payload={
            "cache_path": result.cache_path,
            "response": result.raw_metadata,
        },
        candidate_payload={
            "identity": identity,
            "matched_fields": result.matched_fields,
        },
        vehicle_identity=identity,
        provenance={
            "capture_kind": "local_operator_collection",
            "workbench_job_id": str(job.id),
            "provider": result.provider,
            "verification_rule": "three_independent_sources_minimum_up_to_five",
        },
        extraction_method="local_text_signature_v1",
        confidence=None,
        review_status="pending",
        dedupe_key=dedupe_key,
    )
    session.add(record)
    await session.flush()
    return record


async def _record_source_attempt(
    session: AsyncSession,
    job: CatalogCollectionJob,
    configuration: VehicleConfiguration,
    result: SourceFetchResult,
) -> CatalogWorkbenchSource:
    existing = await session.scalar(
        select(CatalogWorkbenchSource).where(
            CatalogWorkbenchSource.job_id == job.id,
            CatalogWorkbenchSource.vehicle_configuration_id == configuration.id,
            CatalogWorkbenchSource.provider == result.provider,
        )
    )
    if existing is not None:
        return existing

    matched_fields = dict(result.matched_fields)
    if result.fetch_status == "success":
        staging = await _stage_successful_source(session, job, configuration, result)
        matched_fields["staging_record_id"] = str(staging.id)

    item = CatalogWorkbenchSource(
        job_id=job.id,
        vehicle_configuration_id=configuration.id,
        provider=result.provider,
        source_url=result.source_url,
        fetch_status=result.fetch_status,
        http_status=result.http_status,
        matched_fields=matched_fields,
        raw_sha256=result.raw_sha256,
        cache_path=result.cache_path,
        error=result.error,
        fetched_at=_now() if result.fetch_status == "success" else None,
    )
    session.add(item)
    await session.flush()
    return item


async def _promote_matching_evidence(
    session: AsyncSession,
    configuration: VehicleConfiguration,
    matching_sources: list[CatalogWorkbenchSource],
) -> None:
    for source in matching_sources:
        staging_id_raw = source.matched_fields.get("staging_record_id")
        if not isinstance(staging_id_raw, str):
            continue
        staging_id = UUID(staging_id_raw)
        staging = await session.get(CatalogSourceRecord, staging_id)
        if staging is None:
            continue
        staging.review_status = "verified"
        staging.reviewed_at = _now()
        staging.reviewed_by = VERIFIER
        existing = await session.scalar(
            select(CatalogVerifiedEvidence).where(
                CatalogVerifiedEvidence.staging_record_id == staging.id
            )
        )
        if existing is not None:
            continue
        batch = await session.get(CatalogIngestionBatch, staging.batch_id)
        session.add(
            CatalogVerifiedEvidence(
                staging_record_id=staging.id,
                candidate_type=staging.candidate_type,
                verified_payload={
                    "identity": _identity(configuration),
                    "matched_fields": source.matched_fields,
                },
                vehicle_identity=staging.vehicle_identity,
                source_name=batch.source_name if batch is not None else source.provider,
                source_type=batch.source_type if batch is not None else "vehicle_reference",
                source_record_id=staging.source_record_id,
                source_url=staging.source_url,
                raw_sha256=staging.raw_sha256,
                fetched_at=staging.fetched_at,
                observed_at=staging.observed_at,
                provenance=staging.provenance,
                extraction_method=staging.extraction_method,
                promoted_by=VERIFIER,
            )
        )


async def _refresh_job_counts(session: AsyncSession, job: CatalogCollectionJob) -> None:
    rows = (
        await session.execute(
            select(
                CatalogCoverageItem.collection_status,
                CatalogCoverageItem.verification_status,
            )
            .join(
                VehicleConfiguration,
                VehicleConfiguration.id == CatalogCoverageItem.vehicle_configuration_id,
            )
            .where(
                CatalogCoverageItem.batch_id == job.batch_id,
                VehicleConfiguration.make == job.make,
            )
        )
    ).all()
    job.total_items = len(rows)
    job.collected_items = sum(status == "collected" for status, _ in rows)
    job.verified_items = sum(status == "verified" for _, status in rows)
    job.processed_items = max(job.processed_items, job.cursor_position)
    job.last_heartbeat_at = _now()


async def _process_configuration(
    job_id: UUID,
    coverage_item_id: UUID,
    configuration_id: UUID,
) -> bool:
    async with session_factory() as session:
        async with session.begin():
            job = await session.get(CatalogCollectionJob, job_id)
            coverage = await session.get(CatalogCoverageItem, coverage_item_id)
            configuration = await session.get(VehicleConfiguration, configuration_id)
            if job is None or coverage is None or configuration is None:
                return True
            if job.status != "running":
                return False
            coverage.collection_status = "collecting"
            job.last_heartbeat_at = _now()
            await _log(
                session,
                job.id,
                "configuration_started",
                (
                    f"Collecting {configuration.year} {configuration.make} "
                    f"{configuration.model} {configuration.trim or ''}."
                ).strip(),
                details=_identity(configuration),
            )

    for provider, source_url in source_requests(configuration):
        if await _job_status(job_id) != "running":
            return False
        async with session_factory() as session:
            existing = await session.scalar(
                select(CatalogWorkbenchSource).where(
                    CatalogWorkbenchSource.job_id == job_id,
                    CatalogWorkbenchSource.vehicle_configuration_id == configuration_id,
                    CatalogWorkbenchSource.provider == provider,
                )
            )
        if existing is not None:
            continue

        result = await asyncio.to_thread(fetch_source, provider, source_url, configuration)
        async with session_factory() as session:
            async with session.begin():
                job = await session.get(CatalogCollectionJob, job_id)
                current_configuration = await session.get(VehicleConfiguration, configuration_id)
                if job is None or current_configuration is None:
                    return True
                job.last_heartbeat_at = _now()
                source = await _record_source_attempt(
                    session,
                    job,
                    current_configuration,
                    result,
                )
                matched = bool(source.matched_fields.get("configuration_match"))
                level = "info" if result.fetch_status == "success" else "warning"
                await _log(
                    session,
                    job.id,
                    "source_result",
                    (
                        f"{provider}: {result.fetch_status}"
                        + (" · configuration match" if matched else "")
                    ),
                    level=level,
                    details={
                        "vehicle_configuration_id": str(configuration_id),
                        "provider": provider,
                        "source_url": source_url,
                        "fetch_status": result.fetch_status,
                        "http_status": result.http_status,
                        "matched_fields": source.matched_fields,
                        "cache_path": result.cache_path,
                        "error": result.error,
                    },
                )

    async with session_factory() as session:
        async with session.begin():
            job = await session.get(CatalogCollectionJob, job_id)
            coverage = await session.get(CatalogCoverageItem, coverage_item_id)
            configuration = await session.get(VehicleConfiguration, configuration_id)
            if job is None or coverage is None or configuration is None:
                return True
            sources = list(
                await session.scalars(
                    select(CatalogWorkbenchSource)
                    .where(
                        CatalogWorkbenchSource.job_id == job.id,
                        CatalogWorkbenchSource.vehicle_configuration_id == configuration.id,
                    )
                    .order_by(CatalogWorkbenchSource.provider)
                )
            )
            successful = [source for source in sources if source.fetch_status == "success"]
            matching = [
                source
                for source in successful
                if source.matched_fields.get("configuration_match") is True
            ]
            coverage.collection_status = "collected"
            coverage.source_observation_count = len(successful)
            coverage.source_match_count = len(matching)
            coverage.last_collected_at = _now()
            coverage.source_matrix = {
                "rule": "three_independent_sources_minimum_up_to_five",
                "observed_sources": len(successful),
                "configuration_matches": len(matching),
                "sources": [
                    {
                        "provider": source.provider,
                        "url": source.source_url,
                        "fetch_status": source.fetch_status,
                        "matched_fields": source.matched_fields,
                    }
                    for source in sources
                ],
            }
            if len(matching) >= 3:
                coverage.verification_status = "verified"
                coverage.verified_at = _now()
                configuration.verification_status = "verified"
                configuration.identity_source = "multi_source"
                await _promote_matching_evidence(session, configuration, matching)
            job.last_configuration_id = configuration.id
            job.last_heartbeat_at = _now()
            await _log(
                session,
                job.id,
                "configuration_completed",
                (
                    f"Completed {configuration.year} {configuration.make} {configuration.model}: "
                    f"{len(successful)} sources collected, {len(matching)} configuration matches."
                ),
                details={
                    "vehicle_configuration_id": str(configuration.id),
                    "collected_sources": len(successful),
                    "matching_sources": len(matching),
                    "verified": coverage.verification_status == "verified",
                },
            )
            return True


async def _complete_ingestion_batches(session: AsyncSession, job_id: UUID) -> None:
    for provider in PROVIDERS:
        batch = await session.get(CatalogIngestionBatch, _stable_id(f"ingestion:{job_id}:{provider}"))
        if batch is not None and batch.status == "open":
            batch.status = "completed"
            batch.completed_at = _now()


async def _process_job(job_id: UUID) -> None:
    async with session_factory() as session:
        job = await session.get(CatalogCollectionJob, job_id)
        if job is None:
            return
        rows = (
            await session.execute(
                select(CatalogCoverageItem.id, VehicleConfiguration.id)
                .join(
                    VehicleConfiguration,
                    VehicleConfiguration.id == CatalogCoverageItem.vehicle_configuration_id,
                )
                .where(
                    CatalogCoverageItem.batch_id == job.batch_id,
                    VehicleConfiguration.make == job.make,
                )
                .order_by(
                    VehicleConfiguration.year,
                    VehicleConfiguration.model,
                    VehicleConfiguration.trim,
                    VehicleConfiguration.engine,
                    VehicleConfiguration.transmission,
                    VehicleConfiguration.id,
                )
            )
        ).all()
        start_position = min(job.cursor_position, len(rows))

    for index in range(start_position, len(rows)):
        if await _job_status(job_id) != "running":
            return
        coverage_item_id, configuration_id = rows[index]
        completed = await _process_configuration(job_id, coverage_item_id, configuration_id)
        if not completed:
            return
        async with session_factory() as session:
            async with session.begin():
                job = await session.get(CatalogCollectionJob, job_id)
                if job is None:
                    return
                job.cursor_position = index + 1
                job.processed_items = index + 1
                await _refresh_job_counts(session, job)

    async with session_factory() as session:
        async with session.begin():
            job = await session.get(CatalogCollectionJob, job_id)
            if job is None or job.status != "running":
                return
            await _refresh_job_counts(session, job)
            job.status = "completed"
            job.completed_at = _now()
            await _complete_ingestion_batches(session, job.id)
            await _log(
                session,
                job.id,
                "job_completed",
                (
                    f"Completed {job.make}: {job.collected_items}/{job.total_items} collected, "
                    f"{job.verified_items}/{job.total_items} verified."
                ),
                details={
                    "collected_items": job.collected_items,
                    "verified_items": job.verified_items,
                    "total_items": job.total_items,
                },
            )


async def worker_loop() -> None:
    if not settings.workbench_enabled:
        raise RuntimeError(
            "Local catalog workbench is disabled. Set PARTGRAPH_WORKBENCH_ENABLED=true."
        )
    try:
        while True:
            await _recover_interrupted_jobs()
            job_id = await _claim_next_job()
            if job_id is None:
                await asyncio.sleep(settings.workbench_poll_seconds)
                continue
            try:
                await _process_job(job_id)
            except Exception as exc:
                async with session_factory() as session:
                    async with session.begin():
                        job = await session.get(CatalogCollectionJob, job_id)
                        if job is not None:
                            job.status = "failed"
                            job.last_error = str(exc)[:2000]
                            job.last_heartbeat_at = _now()
                            await _log(
                                session,
                                job.id,
                                "job_failed",
                                "Collection job failed; it can be resumed after the cause is fixed.",
                                level="error",
                                details={"error": job.last_error},
                            )
            await asyncio.sleep(0)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(worker_loop())
