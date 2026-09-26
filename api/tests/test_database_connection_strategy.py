import asyncio
import os
import unittest
from contextlib import contextmanager
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from partgraph.config import _database_pooling
from partgraph.database import _engine_options

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
SERVERLESS_PARALLEL_INSTANCES = 24


@contextmanager
def _temporary_environment(**values: str | None):
    previous = {name: os.environ.get(name) for name in values}
    try:
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


class DatabaseConnectionStrategyUnitTests(unittest.TestCase):
    def test_vercel_defaults_to_no_persistent_sqlalchemy_pool(self) -> None:
        with _temporary_environment(PARTGRAPH_DATABASE_POOLING=None):
            self.assertFalse(_database_pooling(running_on_vercel=True))
        options = _engine_options(pooling_enabled=False)
        self.assertIs(options["poolclass"], NullPool)
        self.assertNotIn("pool_size", options)
        self.assertNotIn("max_overflow", options)

    def test_vercel_rejects_accidental_persistent_pool_override(self) -> None:
        with _temporary_environment(PARTGRAPH_DATABASE_POOLING="true"):
            with self.assertRaisesRegex(ValueError, "must be disabled on Vercel"):
                _database_pooling(running_on_vercel=True)

    def test_non_serverless_runtime_keeps_existing_bounded_pool_default(self) -> None:
        with _temporary_environment(PARTGRAPH_DATABASE_POOLING=None):
            self.assertTrue(_database_pooling(running_on_vercel=False))
        self.assertEqual(
            _engine_options(pooling_enabled=True),
            {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 5},
        )

    def test_non_serverless_runtime_can_explicitly_disable_pooling(self) -> None:
        with _temporary_environment(PARTGRAPH_DATABASE_POOLING="false"):
            self.assertFalse(_database_pooling(running_on_vercel=False))


class DatabaseConnectionStrategyRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        database_url = os.getenv(DATABASE_URL_ENV)
        if not database_url:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")
        self.database_url = database_url

    def _serverless_engine(self, application_name: str):
        return create_async_engine(
            self.database_url,
            poolclass=NullPool,
            connect_args={"application_name": application_name},
        )

    async def test_set_local_role_and_owner_context_reset_at_transaction_end(self) -> None:
        engine = self._serverless_engine(f"partgraph-rel003-local-{uuid4().hex[:12]}")
        marker = str(uuid4())
        try:
            async with engine.connect() as connection:
                async with connection.begin():
                    session_user = await connection.scalar(text("SELECT session_user"))
                    await connection.execute(text("SET LOCAL ROLE partgraph_app"))
                    await connection.execute(
                        text("SELECT set_config('partgraph.user_id', :marker, true)"),
                        {"marker": marker},
                    )
                    self.assertEqual(
                        await connection.scalar(text("SELECT current_user")),
                        "partgraph_app",
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT current_setting('partgraph.user_id', true)")
                        ),
                        marker,
                    )

                async with connection.begin():
                    self.assertEqual(
                        await connection.scalar(text("SELECT current_user")),
                        session_user,
                    )
                    reset_marker = await connection.scalar(
                        text("SELECT current_setting('partgraph.user_id', true)")
                    )
                    self.assertNotEqual(reset_marker, marker)
        finally:
            await engine.dispose()

    async def test_parallel_cold_instances_do_not_create_idle_pool_multiplier(self) -> None:
        application_name = f"partgraph-rel003-load-{uuid4().hex[:12]}"
        all_connected = asyncio.Event()
        release_connections = asyncio.Event()
        counter_lock = asyncio.Lock()
        connected = 0

        async def instance_worker() -> None:
            nonlocal connected
            engine = self._serverless_engine(application_name)
            try:
                async with engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
                    async with counter_lock:
                        connected += 1
                        if connected == SERVERLESS_PARALLEL_INSTANCES:
                            all_connected.set()
                    await release_connections.wait()
                    await connection.rollback()
            finally:
                await engine.dispose()

        tasks = [
            asyncio.create_task(instance_worker())
            for _ in range(SERVERLESS_PARALLEL_INSTANCES)
        ]
        inspector = create_async_engine(self.database_url, poolclass=NullPool)
        try:
            await asyncio.wait_for(all_connected.wait(), timeout=15)
            async with inspector.connect() as connection:
                observed = await connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname = current_database() AND application_name = :name"
                    ),
                    {"name": application_name},
                )
            self.assertEqual(observed, SERVERLESS_PARALLEL_INSTANCES)

            release_connections.set()
            await asyncio.gather(*tasks)

            async with inspector.connect() as connection:
                remaining = await connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname = current_database() AND application_name = :name"
                    ),
                    {"name": application_name},
                )
            self.assertEqual(remaining, 0)
        finally:
            release_connections.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            await inspector.dispose()


if __name__ == "__main__":
    unittest.main()
