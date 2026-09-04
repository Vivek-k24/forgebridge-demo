from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..errors import ErrorCode, PartGraphError
from ..identity.vehicle.models import VehicleConfiguration
from .coverage_models import CatalogCoverageBatch, CatalogCoverageItem
from .workbench_models import (
    CatalogCollectionJob,
    CatalogWorkbenchLog,
    CatalogWorkbenchSource,
)
from .workbench_schemas import (
    CatalogCollectionJobRead,
    CatalogWorkbenchDashboardRead,
    CatalogWorkbenchLogRead,
    CatalogWorkbenchMakeRead,
    CatalogWorkbenchSourceRead,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _require_enabled() -> None:
    if not settings.workbench_enabled:
        raise PartGraphError(
            code=ErrorCode.REQUEST_NOT_FOUND,
            message="Local catalog workbench is not enabled on this runtime.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


async def _batch(session: AsyncSession, batch_key: str) -> CatalogCoverageBatch:
    _require_enabled()
    item = await session.scalar(
        select(CatalogCoverageBatch).where(CatalogCoverageBatch.batch_key == batch_key)
    )
    if item is None:
        raise PartGraphError(
            code=ErrorCode.REQUEST_NOT_FOUND,
            message="Catalog coverage batch not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return item


async def _latest_job(
    session: AsyncSession,
    batch_id: UUID,
    make: str,
) -> CatalogCollectionJob | None:
    return await session.scalar(
        select(CatalogCollectionJob)
        .where(
            CatalogCollectionJob.batch_id == batch_id,
            CatalogCollectionJob.make == make,
        )
        .order_by(CatalogCollectionJob.created_at.desc())
        .limit(1)
    )


async def workbench_dashboard(
    session: AsyncSession,
    batch_key: str,
) -> CatalogWorkbenchDashboardRead:
    batch = await _batch(session, batch_key)
    rows = (
        await session.execute(
            select(
                VehicleConfiguration.make,
                CatalogCoverageItem.collection_status,
                CatalogCoverageItem.verification_status,
            )
            .join(
                VehicleConfiguration,
                VehicleConfiguration.id == CatalogCoverageItem.vehicle_configuration_id,
            )
            .where(CatalogCoverageItem.batch_id == batch.id)
        )
    ).all()

    by_make: dict[str, dict[str, int]] = {}
    for make, collection_status, verification_status in rows:
        counters = by_make.setdefault(
            make,
            {"candidates": 0, "collected": 0, "verified": 0, "conflicts": 0},
        )
        counters["candidates"] += 1
        if collection_status == "collected":
            counters["collected"] += 1
        if verification_status == "verified":
            counters["verified"] += 1
        elif verification_status == "conflict":
            counters["conflicts"] += 1

    makes: list[CatalogWorkbenchMakeRead] = []
    for make in sorted(by_make, key=str.casefold):
        counts = by_make[make]
        latest = await _latest_job(session, batch.id, make)
        makes.append(
            CatalogWorkbenchMakeRead(
                make=make,
                candidates=counts["candidates"],
                collected=counts["collected"],
                verified=counts["verified"],
                conflicts=counts["conflicts"],
                collection_percent=_percent(counts["collected"], counts["candidates"]),
                verification_percent=_percent(counts["verified"], counts["candidates"]),
                latest_job=(
                    CatalogCollectionJobRead.model_validate(latest) if latest is not None else None
                ),
            )
        )

    candidates = sum(item.candidates for item in makes)
    collected = sum(item.collected for item in makes)
    verified = sum(item.verified for item in makes)
    conflicts = sum(item.conflicts for item in makes)
    return CatalogWorkbenchDashboardRead(
        batch_key=batch.batch_key,
        label=batch.label,
        verification_rule=batch.verification_rule,
        candidates=candidates,
        collected=collected,
        verified=verified,
        conflicts=conflicts,
        collection_percent=_percent(collected, candidates),
        verification_percent=_percent(verified, candidates),
        makes=makes,
    )


async def start_make_job(
    session: AsyncSession,
    batch_key: str,
    make: str,
) -> CatalogCollectionJobRead:
    batch = await _batch(session, batch_key)
    canonical_make = await session.scalar(
        select(VehicleConfiguration.make)
        .join(
            CatalogCoverageItem,
            CatalogCoverageItem.vehicle_configuration_id == VehicleConfiguration.id,
        )
        .where(
            CatalogCoverageItem.batch_id == batch.id,
            func.lower(VehicleConfiguration.make) == make.casefold(),
        )
        .limit(1)
    )
    if canonical_make is None:
        raise PartGraphError(
            code=ErrorCode.REQUEST_NOT_FOUND,
            message="Make is not part of this catalog batch.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    latest = await _latest_job(session, batch.id, canonical_make)
    if latest is not None and latest.status in {"queued", "running", "paused"}:
        return CatalogCollectionJobRead.model_validate(latest)

    total_items = int(
        await session.scalar(
            select(func.count(CatalogCoverageItem.id))
            .join(
                VehicleConfiguration,
                VehicleConfiguration.id == CatalogCoverageItem.vehicle_configuration_id,
            )
            .where(
                CatalogCoverageItem.batch_id == batch.id,
                VehicleConfiguration.make == canonical_make,
            )
        )
        or 0
    )
    job = CatalogCollectionJob(
        batch_id=batch.id,
        make=canonical_make,
        status="queued",
        cursor_position=0,
        total_items=total_items,
        processed_items=0,
        collected_items=0,
        verified_items=0,
    )
    session.add(job)
    await session.flush()
    session.add(
        CatalogWorkbenchLog(
            job_id=job.id,
            level="info",
            event_type="job_queued",
            message=f"Queued {canonical_make} collection job with {total_items} candidates.",
            details={"batch_key": batch.batch_key, "make": canonical_make},
        )
    )
    await session.commit()
    await session.refresh(job)
    return CatalogCollectionJobRead.model_validate(job)


async def pause_make_job(
    session: AsyncSession,
    batch_key: str,
    make: str,
) -> CatalogCollectionJobRead:
    batch = await _batch(session, batch_key)
    job = await _latest_job(session, batch.id, make)
    if job is None:
        raise PartGraphError(
            code=ErrorCode.REQUEST_NOT_FOUND,
            message="No collection job exists for this make.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if job.status in {"queued", "running"}:
        job.status = "paused"
        job.last_heartbeat_at = _now()
        session.add(
            CatalogWorkbenchLog(
                job_id=job.id,
                level="info",
                event_type="job_paused",
                message=f"Paused {job.make} after the current safe checkpoint.",
                details={"cursor_position": job.cursor_position},
            )
        )
        await session.commit()
        await session.refresh(job)
    return CatalogCollectionJobRead.model_validate(job)


async def resume_make_job(
    session: AsyncSession,
    batch_key: str,
    make: str,
) -> CatalogCollectionJobRead:
    batch = await _batch(session, batch_key)
    job = await _latest_job(session, batch.id, make)
    if job is None:
        raise PartGraphError(
            code=ErrorCode.REQUEST_NOT_FOUND,
            message="No collection job exists for this make.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if job.status in {"paused", "failed"}:
        job.status = "queued"
        job.completed_at = None
        job.last_error = None
        job.last_heartbeat_at = _now()
        session.add(
            CatalogWorkbenchLog(
                job_id=job.id,
                level="info",
                event_type="job_resumed",
                message=f"Queued {job.make} to resume from candidate {job.cursor_position + 1}.",
                details={"cursor_position": job.cursor_position},
            )
        )
        await session.commit()
        await session.refresh(job)
    return CatalogCollectionJobRead.model_validate(job)


async def job_logs(
    session: AsyncSession,
    job_id: UUID,
    limit: int,
) -> list[CatalogWorkbenchLogRead]:
    _require_enabled()
    rows = list(
        await session.scalars(
            select(CatalogWorkbenchLog)
            .where(CatalogWorkbenchLog.job_id == job_id)
            .order_by(CatalogWorkbenchLog.created_at.desc())
            .limit(limit)
        )
    )
    return [CatalogWorkbenchLogRead.model_validate(item) for item in rows]


async def job_sources(
    session: AsyncSession,
    job_id: UUID,
    limit: int,
) -> list[CatalogWorkbenchSourceRead]:
    _require_enabled()
    rows = list(
        await session.scalars(
            select(CatalogWorkbenchSource)
            .where(CatalogWorkbenchSource.job_id == job_id)
            .order_by(CatalogWorkbenchSource.created_at.desc())
            .limit(limit)
        )
    )
    return [CatalogWorkbenchSourceRead.model_validate(item) for item in rows]
