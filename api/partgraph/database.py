import logging
from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from .config import settings
from .observability import emit_event


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


def database_connection_was_invalidated(exc: BaseException) -> bool:
    return isinstance(exc, DBAPIError) and exc.connection_invalidated


engine: AsyncEngine = create_async_engine(settings.database_url, **_engine_options())
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def database_readiness() -> float:
    started = perf_counter()
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        emit_event(
            "database.readiness",
            level=logging.ERROR,
            **{
                "outcome": "failure",
                "database.duration_ms": round((perf_counter() - started) * 1000, 2),
                "exception.type": type(exc).__name__,
            },
        )
        raise

    duration_ms = round((perf_counter() - started) * 1000, 2)
    emit_event(
        "database.readiness",
        **{
            "outcome": "success",
            "database.duration_ms": duration_ms,
        },
    )
    return duration_ms
