from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import engine, session_factory
from ..identity.vehicle.models import VehicleConfiguration
from .coverage_models import CatalogCoverageItem
from .workbench_evidence import (
    complete_ingestion_batches,
    reconcile_configuration,
    record_source_attempt,
    stage_source_result,
    vehicle_identity,
)
from .workbench_models import CatalogCollectionJob, CatalogWorkbenchLog, CatalogWorkbenchSource
from .workbench_source_pipeline import (
    SourceFetchResult,
    SourceRequest,
    fetch_source,
    replay_cached_source,
    source_requests,
)

STALE_JOB_SECONDS = 60
ACCESS_BLOCK_THRESHOLD = 3
_provider_block_counts: dict[str, int] = {}
_provider_circuit_open: set[str] = set()


def _now() -> datetime:
    return datetime.now(UTC)


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


async def _recover_interrupted_jobs() -> None:
    cutoff = _now() - timedelta(seconds=STALE_JOB_SECONDS)
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
                    f"Recovered interrupted {job.make} job at candidate {job.cursor_position + 1}.",
                    level="warning",
                    details={"cursor_position": job.cursor_position},
                )


async def _claim_job() -> UUID | None:
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
            job.status = "running"
            job.started_at = job.started_at or _now()
            job.last_heartbeat_at = _now()
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


async def _cached_result(
    session: AsyncSession,
    request: SourceRequest,
    configuration: VehicleConfiguration,
) -> SourceFetchResult | None:
    cached = await session.scalar(
        select(CatalogWorkbenchSource)
        .where(
            CatalogWorkbenchSource.provider == request.source_key,
            CatalogWorkbenchSource.source_url == request.source_url,
            CatalogWorkbenchSource.fetch_status == "success",
            CatalogWorkbenchSource.cache_path.is_not(None),
        )
        .order_by(CatalogWorkbenchSource.fetched_at.desc(), CatalogWorkbenchSource.created_at.desc())
        .limit(1)
    )
    if cached is None or cached.cache_path is None:
        return None
    return replay_cached_source(request, cached.cache_path, configuration)


def _circuit_result(request: SourceRequest) -> SourceFetchResult:
    return SourceFetchResult(
        provider=request.source_key,
        source_class=request.source_class,
        source_url=request.source_url,
        fetch_status="blocked",
        http_status=None,
        matched_fields={},
        field_observations={},
        raw_sha256=None,
        cache_path=None,
        error="Source circuit open after repeated access-control responses; no bypass attempted.",
        raw_metadata={"circuit_open": True},
    )


def _track_block(result: SourceFetchResult) -> None:
    if result.fetch_status != "blocked":
        return
    count = _provider_block_counts.get(result.provider, 0) + 1
    _provider_block_counts[result.provider] = count
    if count >= ACCESS_BLOCK_THRESHOLD:
        _provider_circuit_open.add(result.provider)


async def _fetch_or_reuse(
    request: SourceRequest,
    configuration: VehicleConfiguration,
) -> SourceFetchResult:
    async with session_factory() as session:
        cached = await _cached_result(session, request, configuration)
    if cached is not None:
        return cached
    if request.source_key in _provider_circuit_open:
        return _circuit_result(request)
    result = await asyncio.to_thread(fetch_source, request, configuration)
    _track_block(result)
    return result


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
    job.collected_items = sum(collection == "collected" for collection, _ in rows)
    job.verified_items = sum(verification == "verified" for _, verification in rows)
    job.processed_items = max(job.processed_items, job.cursor_position)
    job.last_heartbeat_at = _now()


async def _process_configuration(
    job_id: UUID,
    coverage_id: UUID,
    configuration_id: UUID,
) -> bool:
    async with session_factory() as session:
        async with session.begin():
            job = await session.get(CatalogCollectionJob, job_id)
            coverage = await session.get(CatalogCoverageItem, coverage_id)
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
                details=vehicle_identity(configuration),
            )

    async with session_factory() as session:
        configuration = await session.get(VehicleConfiguration, configuration_id)
        requests = source_requests(configuration) if configuration is not None else ()

    for request in requests:
        if await _job_status(job_id) != "running":
            return False
        async with session_factory() as session:
            existing = await session.scalar(
                select(CatalogWorkbenchSource).where(
                    CatalogWorkbenchSource.job_id == job_id,
                    CatalogWorkbenchSource.vehicle_configuration_id == configuration_id,
                    CatalogWorkbenchSource.provider == request.source_key,
                )
            )
        if existing is not None:
            continue

        async with session_factory() as session:
            configuration = await session.get(VehicleConfiguration, configuration_id)
        if configuration is None:
            return True
        result = await _fetch_or_reuse(request, configuration)

        async with session_factory() as session:
            async with session.begin():
                job = await session.get(CatalogCollectionJob, job_id)
                configuration = await session.get(VehicleConfiguration, configuration_id)
                if job is None or configuration is None:
                    return True
                source = await record_source_attempt(session, job, configuration, result)
                job.last_heartbeat_at = _now()
                observed = source.matched_fields.get("observed_fields")
                observed_count = len(observed) if isinstance(observed, list) else 0
                level = "info" if result.fetch_status == "success" else "warning"
                await _log(
                    session,
                    job.id,
                    "source_result",
                    (
                        f"{request.source_key}: {result.fetch_status} · "
                        f"{observed_count} fields observed"
                    ),
                    level=level,
                    details={
                        "vehicle_configuration_id": str(configuration.id),
                        "provider": request.source_key,
                        "source_url": request.source_url,
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
            coverage = await session.get(CatalogCoverageItem, coverage_id)
            configuration = await session.get(VehicleConfiguration, configuration_id)
            if job is None or coverage is None or configuration is None:
                return True
            sources = list(
                await session.scalars(
                    select(CatalogWorkbenchSource).where(
                        CatalogWorkbenchSource.job_id == job.id,
                        CatalogWorkbenchSource.vehicle_configuration_id == configuration.id,
                    )
                )
            )
            coverage.collection_status = "collected"
            coverage.last_collected_at = _now()
            reconciliation = await reconcile_configuration(session, coverage, configuration)
            job.last_configuration_id = configuration.id
            job.last_heartbeat_at = _now()
            summary = reconciliation.get("summary")
            summary = summary if isinstance(summary, dict) else {}
            await _log(
                session,
                job.id,
                "configuration_completed",
                (
                    f"Completed {configuration.year} {configuration.make} {configuration.model}: "
                    f"{len(sources)} source attempts, {summary.get('verified_fields', 0)} "
                    "verified fields."
                ),
                details={
                    "vehicle_configuration_id": str(configuration.id),
                    "source_attempts": len(sources),
                    "field_summary": summary,
                    "configuration_verified": coverage.verification_status == "verified",
                },
            )
    return True


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
        start = min(job.cursor_position, len(rows))

    for index in range(start, len(rows)):
        if await _job_status(job_id) != "running":
            return
        coverage_id, configuration_id = rows[index]
        if not await _process_configuration(job_id, coverage_id, configuration_id):
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
            await complete_ingestion_batches(session, job.id)
            await _log(
                session,
                job.id,
                "job_completed",
                (
                    f"Completed {job.make}: {job.collected_items}/{job.total_items} collected, "
                    f"{job.verified_items}/{job.total_items} configurations verified."
                ),
                details={
                    "collected_items": job.collected_items,
                    "verified_items": job.verified_items,
                    "total_items": job.total_items,
                },
            )


async def reprocess_cached_sources() -> None:
    """Run the v2 extractor/reconciler over existing raw cache with zero web requests."""
    if not settings.workbench_enabled:
        raise RuntimeError("Local catalog workbench is disabled.")

    async with session_factory() as session:
        rows = (
            await session.execute(
                select(CatalogWorkbenchSource.id)
                .where(
                    CatalogWorkbenchSource.fetch_status == "success",
                    CatalogWorkbenchSource.cache_path.is_not(None),
                )
                .order_by(CatalogWorkbenchSource.created_at.desc())
            )
        ).scalars().all()

    seen: set[tuple[UUID, str, str]] = set()
    touched: set[UUID] = set()
    replayed = 0
    for source_id in rows:
        async with session_factory() as session:
            async with session.begin():
                source = await session.get(CatalogWorkbenchSource, source_id)
                if source is None or source.cache_path is None:
                    continue
                key = (source.vehicle_configuration_id, source.provider, source.source_url)
                if key in seen:
                    continue
                seen.add(key)
                job = await session.get(CatalogCollectionJob, source.job_id)
                configuration = await session.get(
                    VehicleConfiguration,
                    source.vehicle_configuration_id,
                )
                if job is None or configuration is None:
                    continue
                request = next(
                    (
                        item
                        for item in source_requests(configuration)
                        if item.source_key == source.provider
                    ),
                    SourceRequest(
                        source.provider,
                        (
                            "government"
                            if source.provider in {"nhtsa_vpic", "fueleconomy_gov"}
                            else "vehicle_reference"
                        ),
                        source.source_url,
                    ),
                )
                replay = replay_cached_source(request, source.cache_path, configuration)
                if replay is None:
                    continue
                staged = await stage_source_result(session, job, configuration, replay)
                enriched = dict(replay.matched_fields)
                enriched["source_class"] = replay.source_class
                if staged is not None:
                    enriched["staging_record_id"] = str(staged.id)
                enriched["cache_reprocessed"] = True
                source.matched_fields = enriched
                touched.add(configuration.id)
                replayed += 1

    for configuration_id in sorted(touched, key=str):
        async with session_factory() as session:
            async with session.begin():
                configuration = await session.get(VehicleConfiguration, configuration_id)
                coverage = await session.scalar(
                    select(CatalogCoverageItem).where(
                        CatalogCoverageItem.vehicle_configuration_id == configuration_id
                    )
                )
                if configuration is not None and coverage is not None:
                    await reconcile_configuration(session, coverage, configuration)

    print(
        f"Reprocessed {replayed} cached source captures across "
        f"{len(touched)} configurations; no web requests were made."
    )


async def worker_loop() -> None:
    if not settings.workbench_enabled:
        raise RuntimeError("Local catalog workbench is disabled.")
    try:
        while True:
            await _recover_interrupted_jobs()
            job_id = await _claim_job()
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


def main() -> None:
    parser = argparse.ArgumentParser(description="PartGraph local catalog worker")
    parser.add_argument(
        "--reprocess-cache",
        action="store_true",
        help="Re-extract/reconcile existing cached sources without web requests.",
    )
    args = parser.parse_args()
    asyncio.run(reprocess_cached_sources() if args.reprocess_cache else worker_loop())


if __name__ == "__main__":
    main()
