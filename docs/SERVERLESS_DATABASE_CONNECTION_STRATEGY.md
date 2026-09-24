# Serverless Database Connection Strategy

PartGraph uses different SQLAlchemy connection behavior for serverless and long-lived runtimes.

## Vercel runtime

When `VERCEL=1`, PartGraph disables the persistent SQLAlchemy client pool by default and creates the engine with `NullPool`. `PARTGRAPH_DATABASE_POOLING=true` is rejected on Vercel so an environment override cannot silently restore the previous per-instance `5 + 5 overflow` pool.

With `NullPool`, each active SQLAlchemy connection maps to one PostgreSQL connection and is closed when that connection scope ends. A warm Vercel function therefore does not retain an idle PostgreSQL pool between requests. This removes the multiplicative failure mode where every serverless instance could independently reserve up to ten database connections.

The current Neon preview and production computes are still direct endpoints; this remediation does not mutate production infrastructure or enable Neon transaction pooling. A future switch to the Neon pooled endpoint must be an explicit environment/infrastructure change and must preserve the transaction-scoped security model described below.

## Long-lived local/container runtime

Outside Vercel, PartGraph retains the existing bounded SQLAlchemy pool by default:

- `pool_size = 5`
- `max_overflow = 5`
- `pool_pre_ping = true`

`PARTGRAPH_DATABASE_POOLING=false` can still disable that pool explicitly for a non-serverless runtime.

## Transaction-local authorization semantics

Authenticated PartGraph work relies on PostgreSQL transaction-local state, including `SET LOCAL ROLE partgraph_app` and `set_config('partgraph.user_id', ..., true)`. The database reliability test proves both values apply inside the transaction and reset when the transaction ends. No request authorization state is intentionally stored with session-wide `SET` semantics.

This transaction-local design is compatible with the current `NullPool` strategy and is also the required contract if PartGraph later adopts an external transaction pooler.

## Connection-bound load test

`api/tests/test_database_connection_strategy.py` contains a serverless-shaped concurrency test. It creates 24 independent SQLAlchemy engines with `NullPool`, representing 24 simultaneous cold function instances, opens one active connection per instance, and measures the matching PostgreSQL backends through `pg_stat_activity`.

Acceptance requires:

- exactly one tagged PostgreSQL connection per active simulated instance;
- no hidden client-pool multiplier;
- zero tagged idle connections after all simulated instances release their connections; and
- transaction-local role/user context to reset after commit.

The permanent `.github/workflows/database-reliability.yml` gate runs this test against a fresh migrated PostgreSQL database.

## Scaling boundary

`NullPool` removes per-instance idle-pool multiplication; it does not make PostgreSQL connection capacity unlimited. Total active database connections can still approach the number of concurrent requests doing database work. Before PartGraph raises Vercel concurrency to a level that could challenge Neon connection limits, the project should explicitly enable and validate Neon's transaction pooler or another approved external pooling layer, then repeat this concurrency test at the intended deployment scale.
