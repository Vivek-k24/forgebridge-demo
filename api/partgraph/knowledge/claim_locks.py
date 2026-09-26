from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def lock_mechanical_claim_scope(
    session: AsyncSession,
    conflict_key: str,
) -> None:
    """Serialize curator mutations for one deterministic mechanical fact scope."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"mechanical-claim-scope:{conflict_key}"},
    )


async def lock_mechanical_claims(
    session: AsyncSession,
    claim_ids: Iterable[UUID],
    *,
    shared: bool,
) -> None:
    """Lock claims without granting a read-only publisher table UPDATE rights.

    Materialization takes shared locks while curator state transitions take
    exclusive locks. Sorting gives every multi-claim transaction the same lock
    order and avoids lock-order inversions between concurrent requests.
    """
    lock_function = (
        "pg_advisory_xact_lock_shared" if shared else "pg_advisory_xact_lock"
    )
    statement = text(f"SELECT {lock_function}(hashtextextended(:key, 0))")
    for claim_id in sorted(set(claim_ids), key=str):
        await session.execute(
            statement,
            {"key": f"mechanical-claim:{claim_id}"},
        )
