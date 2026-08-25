from time import perf_counter

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .config import settings


engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)


async def database_readiness() -> float:
    started = perf_counter()
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return round((perf_counter() - started) * 1000, 2)
