from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..identity.vehicle.models import VehicleConfiguration
from .coverage_models import CatalogCoverageBatch, CatalogCoverageItem
from .coverage_schemas import CatalogCoverageBatchRead, CatalogCoverageMakeProgress


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


async def _batch_read(
    session: AsyncSession,
    batch: CatalogCoverageBatch,
) -> CatalogCoverageBatchRead:
    rows = (
        await session.execute(
            select(
                CatalogCoverageItem.collection_status,
                CatalogCoverageItem.verification_status,
                VehicleConfiguration.make,
            )
            .join(
                VehicleConfiguration,
                VehicleConfiguration.id == CatalogCoverageItem.vehicle_configuration_id,
            )
            .where(CatalogCoverageItem.batch_id == batch.id)
        )
    ).all()

    counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"candidates": 0, "collected": 0, "verified": 0, "conflict": 0}
    )
    for collection_status, verification_status, make in rows:
        item = counts[make]
        item["candidates"] += 1
        if collection_status == "collected":
            item["collected"] += 1
        if verification_status == "verified":
            item["verified"] += 1
        elif verification_status == "conflict":
            item["conflict"] += 1

    make_progress = [
        CatalogCoverageMakeProgress(
            make=make,
            candidates=item["candidates"],
            collected=item["collected"],
            verified=item["verified"],
            conflict=item["conflict"],
            collection_remaining=item["candidates"] - item["collected"],
            verification_remaining=item["candidates"] - item["verified"],
            collection_percent=_percent(item["collected"], item["candidates"]),
            verification_percent=_percent(item["verified"], item["candidates"]),
        )
        for make, item in sorted(counts.items(), key=lambda pair: pair[0].casefold())
    ]
    candidates = sum(item.candidates for item in make_progress)
    collected = sum(item.collected for item in make_progress)
    verified = sum(item.verified for item in make_progress)
    conflict = sum(item.conflict for item in make_progress)

    return CatalogCoverageBatchRead(
        id=batch.id,
        batch_key=batch.batch_key,
        label=batch.label,
        target_rows=batch.target_rows,
        verification_rule=batch.verification_rule,
        status=batch.status,
        scope=batch.scope,
        candidates=candidates,
        collected=collected,
        verified=verified,
        conflict=conflict,
        collection_remaining=candidates - collected,
        verification_remaining=candidates - verified,
        collection_percent=_percent(collected, candidates),
        verification_percent=_percent(verified, candidates),
        makes=make_progress,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


async def list_coverage_batches(session: AsyncSession) -> list[CatalogCoverageBatchRead]:
    batches = list(
        await session.scalars(
            select(CatalogCoverageBatch).order_by(CatalogCoverageBatch.created_at.desc())
        )
    )
    return [await _batch_read(session, batch) for batch in batches]


async def get_coverage_batch(
    session: AsyncSession,
    batch_key: str,
) -> CatalogCoverageBatchRead | None:
    batch = await session.scalar(
        select(CatalogCoverageBatch).where(CatalogCoverageBatch.batch_key == batch_key)
    )
    if batch is None:
        return None
    return await _batch_read(session, batch)