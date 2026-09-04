from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..identity.vehicle.models import VehicleConfiguration
from .coverage_models import CatalogCoverageBatch, CatalogCoverageItem
from .coverage_schemas import CatalogCoverageBatchRead, CatalogCoverageMakeProgress


def _percent(verified: int, collected: int) -> float:
    if collected <= 0:
        return 0.0
    return round((verified / collected) * 100, 1)


async def _batch_read(
    session: AsyncSession,
    batch: CatalogCoverageBatch,
) -> CatalogCoverageBatchRead:
    rows = (
        await session.execute(
            select(
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
        lambda: {"collected": 0, "verified": 0, "conflict": 0}
    )
    for verification_status, make in rows:
        item = counts[make]
        item["collected"] += 1
        if verification_status == "verified":
            item["verified"] += 1
        elif verification_status == "conflict":
            item["conflict"] += 1

    make_progress = [
        CatalogCoverageMakeProgress(
            make=make,
            collected=item["collected"],
            verified=item["verified"],
            conflict=item["conflict"],
            remaining=item["collected"] - item["verified"],
            verification_percent=_percent(item["verified"], item["collected"]),
        )
        for make, item in sorted(counts.items(), key=lambda pair: pair[0].casefold())
    ]
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
        collected=collected,
        verified=verified,
        conflict=conflict,
        remaining=collected - verified,
        verification_percent=_percent(verified, collected),
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
