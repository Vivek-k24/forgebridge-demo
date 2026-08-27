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

## Vehicle identity foundation

The first domain module is `api/partgraph/vehicle`.

PartGraph is multi-brand from the skeleton onward. Current market scope is the United States and Canada. A vehicle identity request is processed before it reaches canonical storage:

1. market and make aliases are resolved against an explicit supported taxonomy;
2. case, whitespace, punctuation, body-style wording, transmission wording, drivetrain wording, generation wording, and common engine notation are canonicalized deterministically;
3. the processor looks for an exact or compatible canonical configuration;
4. compatible partial information enriches one existing configuration;
5. conflicting facts create distinct variants;
6. ambiguous partial input is rejected instead of guessed.

Manual vehicle configurations remain explicitly `unverified`. Canonicalization prevents duplicate wording from becoming duplicate identities; it does not prove fitment.

European premium/luxury brands are currently excluded by product scope. The supported brand registry lives in `api/partgraph/vehicle/taxonomy.py`.

Database changes are versioned with Alembic. Migration `0002_canonical_vehicle_identity` intentionally replaces the earlier Block 2 manual-test identity table so incorrect tuple-based test duplicates do not become permanent canonical data. No collected catalog data is affected.

## Run locally

Requirements: Docker Desktop with Docker Compose.

```bash
docker compose up --build
```

Open:

- Web: `http://localhost:5173`
- API readiness: `http://localhost:8000/api/v1/health/ready`
- Supported brands: `http://localhost:8000/api/v1/vehicle-brands`
- Vehicle configurations: `http://localhost:8000/api/v1/vehicle-configurations`
- API docs: `http://localhost:8000/docs`

Try entering the same physical vehicle using equivalent wording such as `US` vs `United States`, `4 Dr Sedan` vs `Sedan`, or `CVT` vs `continuously variable transmission`. PartGraph should resolve one canonical configuration. If the input could describe more than one existing variant, the API returns a conflict and asks for more detail rather than merging them.

Stop with:

```bash
docker compose down
```

The PostgreSQL volume is retained between runs, so canonical configuration records survive container restarts. Use `docker compose down -v` only when intentionally resetting local database data.

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
