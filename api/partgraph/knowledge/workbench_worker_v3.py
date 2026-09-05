from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
from uuid import UUID

from sqlalchemy import select

from ..config import settings
from ..database import engine, session_factory
from ..identity.vehicle.models import VehicleConfiguration
from ..identity.vehicle.reconciliation import reconcile_vehicle_specification_profile
from .coverage_models import CatalogCoverageItem
from .workbench_adaptive import (
    GapAnalysis,
    PlannedSourceRequest,
    analyze_gaps,
    fetch_source_adaptive,
    plan_source_requests,
)
from .workbench_evidence import (
    complete_ingestion_batches,
    reconcile_configuration,
    record_source_attempt,
    vehicle_identity,
)
from .workbench_models import CatalogCollectionJob, CatalogWorkbenchSource
from .workbench_source_pipeline import SourceFetchResult, SourceRequest
from .workbench_worker_v2 import (
    _cached_result,
    _circuit_result,
    _claim_job,
    _job_status,
    _log,
    _now,
    _provider_circuit_open,
    _recover_interrupted_jobs,
    _refresh_job_counts,
    _track_block,
    reprocess_cached_sources,
)


async def _fetch_or_reuse_adaptive(
    request: SourceRequest,
    configuration: VehicleConfiguration,
) -> SourceFetchResult:
    async with session_factory() as session:
        cached = await _cached_result(session, request, configuration)

    # A successful cached response normally wins immediately. FuelEconomy is
    # the one proven exception: some valid models (for example historic CR-V)
    # return an empty direct options bundle because the source expands the
    # model name into drivetrain variants. In that case run deterministic
    # model-menu discovery instead of repeatedly replaying an empty bundle.
    if cached is not None and (
        request.source_key != "fueleconomy_gov" or cached.field_observations
    ):
        return cached

    if request.source_key in _provider_circuit_open:
        return _circuit_result(request)

    result = await asyncio.to_thread(
        fetch_source_adaptive,
        request,
        configuration,
        primary_result=cached,
    )
    _track_block(result)
    return result


def _annotate_result(
    result: SourceFetchResult,
    plan: PlannedSourceRequest,
) -> SourceFetchResult:
    matched = dict(result.matched_fields)
    matched["collection_phase"] = plan.phase
    matched["requested_fields"] = list(plan.requested_fields)
    matched["capability_groups"] = list(plan.capability_groups)
    metadata = dict(result.raw_metadata)
    metadata["collection_phase"] = plan.phase
    metadata["requested_fields"] = list(plan.requested_fields)
    metadata["capability_groups"] = list(plan.capability_groups)
    return replace(result, matched_fields=matched, raw_metadata=metadata)


async def _planning_state(
    job_id: UUID,
    configuration_id: UUID,
) -> tuple[
    VehicleConfiguration | None,
    GapAnalysis,
    dict[str, set[str]],
    set[str],
]:
    async with session_factory() as session:
        configuration = await session.get(VehicleConfiguration, configuration_id)
        if configuration is None:
            return None, GapAnalysis((), ()), {}, set()

        reconciliation = await reconcile_vehicle_specification_profile(
            session, configuration.id
        )
        raw_fields = reconciliation.get("fields")
        fields = (
            [item for item in raw_fields if isinstance(item, dict)]
            if isinstance(raw_fields, list)
            else []
        )
        gaps = analyze_gaps(configuration, fields)

        rows = (
            await session.execute(
                select(
                    CatalogWorkbenchSource.job_id,
                    CatalogWorkbenchSource.provider,
                    CatalogWorkbenchSource.matched_fields,
                ).where(
                    CatalogWorkbenchSource.vehicle_configuration_id
                    == configuration_id
                )
            )
        ).all()

    observed_by_provider: dict[str, set[str]] = {}
    attempted_current: set[str] = set()
    for row_job_id, provider, matched_fields in rows:
        if row_job_id == job_id:
            attempted_current.add(provider)
        if not isinstance(matched_fields, dict):
            continue
        observed = matched_fields.get("observed_fields")
        if isinstance(observed, list):
            bucket = observed_by_provider.setdefault(provider, set())
            bucket.update(str(field) for field in observed if isinstance(field, str))

    return configuration, gaps, observed_by_provider, attempted_current


async def _collect_plan(
    job_id: UUID,
    configuration_id: UUID,
    plan: PlannedSourceRequest,
) -> bool:
    if await _job_status(job_id) != "running":
        return False

    async with session_factory() as session:
        configuration = await session.get(VehicleConfiguration, configuration_id)
    if configuration is None:
        return True

    result = await _fetch_or_reuse_adaptive(plan.request, configuration)
    result = _annotate_result(result, plan)

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
                    f"{plan.phase} · {plan.request.source_key}: {result.fetch_status} · "
                    f"{observed_count} fields observed"
                ),
                level=level,
                details={
                    "vehicle_configuration_id": str(configuration.id),
                    "provider": plan.request.source_key,
                    "source_url": plan.request.source_url,
                    "collection_phase": plan.phase,
                    "requested_fields": list(plan.requested_fields),
                    "capability_groups": list(plan.capability_groups),
                    "fetch_status": result.fetch_status,
                    "http_status": result.http_status,
                    "matched_fields": source.matched_fields,
                    "cache_path": result.cache_path,
                    "error": result.error,
                },
            )
    return True


async def _run_phase(
    job_id: UUID,
    configuration_id: UUID,
    *,
    phase: str,
) -> bool:
    while True:
        if await _job_status(job_id) != "running":
            return False

        configuration, gaps, observed_by_provider, attempted = await _planning_state(
            job_id, configuration_id
        )
        if configuration is None:
            return True

        plans = plan_source_requests(
            configuration,
            gaps,
            observed_by_provider,
            attempted,
            phase=phase,
        )
        if not plans:
            return True

        plan = plans[0]
        async with session_factory() as session:
            async with session.begin():
                job = await session.get(CatalogCollectionJob, job_id)
                if job is not None:
                    await _log(
                        session,
                        job.id,
                        "adaptive_plan",
                        (
                            f"{phase} source {plan.request.source_key} selected for "
                            f"{', '.join(plan.capability_groups)}."
                        ),
                        details={
                            "vehicle_configuration_id": str(configuration_id),
                            "phase": phase,
                            "provider": plan.request.source_key,
                            "requested_fields": list(plan.requested_fields),
                            "capability_groups": list(plan.capability_groups),
                            "core_gaps": list(gaps.core_fields),
                            "enrichment_gaps": list(gaps.enrichment_fields),
                        },
                    )
        if not await _collect_plan(job_id, configuration_id, plan):
            return False


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
                    f"Adaptive collection for {configuration.year} {configuration.make} "
                    f"{configuration.model} {configuration.trim or ''}."
                ).strip(),
                details=vehicle_identity(configuration),
            )

    # Phase 1: broad, high-yield sources. Every retrieved page is still fully
    # extracted so one network request can contribute many technical facts.
    if not await _run_phase(job_id, configuration_id, phase="broad"):
        return False

    # Phase 2: only sources whose declared capabilities intersect unresolved
    # fields. This is the precision pass; adding future OEM/parts/technical
    # adapters here does not require changing the worker algorithm.
    if not await _run_phase(job_id, configuration_id, phase="gap"):
        return False

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
                        CatalogWorkbenchSource.vehicle_configuration_id
                        == configuration.id,
                    )
                )
            )
            coverage.collection_status = "collected"
            coverage.last_collected_at = _now()
            reconciliation = await reconcile_configuration(
                session, coverage, configuration
            )
            job.last_configuration_id = configuration.id
            job.last_heartbeat_at = _now()
            summary = reconciliation.get("summary")
            summary = summary if isinstance(summary, dict) else {}
            raw_fields = reconciliation.get("fields")
            fields = (
                [item for item in raw_fields if isinstance(item, dict)]
                if isinstance(raw_fields, list)
                else []
            )
            remaining = analyze_gaps(configuration, fields)
            await _log(
                session,
                job.id,
                "configuration_completed",
                (
                    f"Completed {configuration.year} {configuration.make} {configuration.model}: "
                    f"{len(sources)} source attempts this run, "
                    f"{summary.get('verified_fields', 0)} verified fields, "
                    f"{len(remaining.core_fields)} core gaps remain."
                ),
                details={
                    "vehicle_configuration_id": str(configuration.id),
                    "source_attempts": len(sources),
                    "field_summary": summary,
                    "remaining_core_fields": list(remaining.core_fields),
                    "remaining_enrichment_fields": list(remaining.enrichment_fields),
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
                    VehicleConfiguration.id
                    == CatalogCoverageItem.vehicle_configuration_id,
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
                    f"Completed adaptive {job.make} collection: "
                    f"{job.collected_items}/{job.total_items} collected, "
                    f"{job.verified_items}/{job.total_items} configurations verified."
                ),
                details={
                    "collected_items": job.collected_items,
                    "verified_items": job.verified_items,
                    "total_items": job.total_items,
                    "strategy": "broad_then_capability_gap_fill",
                },
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
                                (
                                    "Adaptive collection failed; it can be resumed "
                                    "after the cause is fixed."
                                ),
                                level="error",
                                details={"error": job.last_error},
                            )
            await asyncio.sleep(0)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PartGraph adaptive local catalog worker"
    )
    parser.add_argument(
        "--reprocess-cache",
        action="store_true",
        help="Re-extract/reconcile existing cached sources without web requests.",
    )
    args = parser.parse_args()
    asyncio.run(reprocess_cached_sources() if args.reprocess_cache else worker_loop())


if __name__ == "__main__":
    main()
