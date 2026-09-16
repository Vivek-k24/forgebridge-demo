from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from .config import settings


class Base(DeclarativeBase):
    pass


def _engine_options(*, pooling_enabled: bool | None = None) -> dict[str, Any]:
    enabled = settings.database_pooling if pooling_enabled is None else pooling_enabled
    if not enabled:
        return {"poolclass": NullPool}
    return {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 5,
    }


engine: AsyncEngine = create_async_engine(settings.database_url, **_engine_options())
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def database_readiness() -> float:
    started = perf_counter()
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return round((perf_counter() - started) * 1000, 2)
