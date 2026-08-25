# PartGraph

PartGraph is a stateful AI-assisted repair companion that reconstructs the exact vehicle assembly, tracks every part and repair action as you work, and lets you stop for days or weeks and resume from the same step, same part, and same fastener.

## Current architecture

```text
web (React/TypeScript)
        ↓
api (Python/FastAPI modular monolith)
        ↓
PostgreSQL

collector (separate service, not implemented yet)
```

The collector remains outside the interactive user path. No catalog collection runs in the current application.

## Block 2 — vehicle identity

Block 2 adds the first real domain module: `api/partgraph/vehicle`.

A vehicle configuration records year, market, make, model, and optional generation/trim/body/engine/transmission/drivetrain fields. Manual entries are normalized for deterministic deduplication and persisted in PostgreSQL, but remain explicitly `unverified`. Deduplication is not fitment verification.

Database changes are versioned with Alembic. The API container applies migrations before starting FastAPI.

## Run locally

Requirements: Docker Desktop with Docker Compose.

```bash
docker compose up --build
```

Open:

- Web: `http://localhost:5173`
- API readiness: `http://localhost:8000/api/v1/health/ready`
- Vehicle configurations: `http://localhost:8000/api/v1/vehicle-configurations`
- API docs: `http://localhost:8000/docs`

In the web page, enter a vehicle configuration and save it. Re-enter the same values with different casing or extra whitespace; the API should match the existing configuration ID rather than create a duplicate.

Stop with:

```bash
docker compose down
```

The PostgreSQL volume is retained between runs, so stored configuration records survive container restarts. Use `docker compose down -v` only when intentionally resetting local database data.

## Performance contract

The normal interactive workflow target is p95 under 3 seconds. Ten seconds is a hard blocking boundary, not a target. Collector work, model training, deployments, and LLM calls must never be on the repair-session critical path.

## Current technology baseline

- React 19
- Vite 8
- TypeScript 6
- Python 3.14
- FastAPI
- SQLAlchemy 2
- Alembic
- PostgreSQL 18

Production deployment remains disabled while the rebuild is reviewed block by block.
