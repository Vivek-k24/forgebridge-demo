# PartGraph

PartGraph is a stateful AI-assisted repair companion that reconstructs the exact vehicle assembly, tracks every part and repair action as work progresses, and lets a repair resume from the same physical state after a pause.

## Current architecture

```text
web (React / TypeScript / Nginx)
        ↓
api (Python / FastAPI modular monolith)
        ↓
PostgreSQL

collector (separate service, not implemented yet)
```

The collector remains outside the interactive user path. No catalog collection runs in the current application.

## Vehicle identity foundation

PartGraph is multi-brand from the skeleton onward. Current market scope is the United States and Canada, with supported model years from 1996 through the current calendar year.

The vehicle selector is read-only against shared canonical data:

1. market and make are controlled by the supported taxonomy;
2. year, model, trim, and optional generation are used to search known configurations;
3. model/trim wording is normalized deterministically for comparison;
4. generation is supporting metadata and is not required to establish a fitment match;
5. ambiguous variants are surfaced instead of guessed;
6. unknown manual model/trim text remains a candidate and does not create shared canonical truth.

The VIN tab currently validates VIN format only. External VIN decoding belongs to the later private `UserVehicle` layer after authentication and user isolation exist.

## Catalog trust boundary

Catalog collection is not implemented or invoked yet. PostgreSQL now contains a separate `catalog_staging` schema for future collector output.

- `catalog_staging.ingestion_batches` records source and ingestion-run provenance.
- `catalog_staging.source_records` preserves raw evidence, normalized candidate data, vehicle context, extraction method, confidence, timestamps, review state, and deterministic deduplication.
- `public.catalog_verified_evidence` is an immutable snapshot created only by an explicit verification/promotion operation. It is evidence for future canonical catalog entities; it is not itself a claim that a part or fitment is mechanically correct.
- the database group role `partgraph_collector` can write the staging schema but has no write privilege on canonical vehicle data or verified evidence.
- rejected staging records cannot be promoted in place, and identical source evidence is idempotently deduplicated.

There is intentionally no public staging/promotion API before authentication and administrative authorization exist. The preserved historical catalog artifact is not imported or modified by this block.

## Run locally

Requirements: Docker Desktop with Docker Compose.

```bash
docker compose up --build
```

Open:

- Web: `http://localhost:5173`
- API readiness: `http://localhost:8000/api/v1/health/ready`
- Supported brands: `http://localhost:8000/api/v1/vehicle-brands`
- API docs: `http://localhost:8000/docs`

The production Web container serves the built React application through Nginx. Browser `/api/...` requests are reverse-proxied to the API container, while direct local API access remains available on port 8000.

Stop with:

```bash
docker compose down
```

The PostgreSQL volume is retained between runs. Use `docker compose down -v` only when intentionally deleting local database data.

## CI/CD

GitHub Actions is the automated quality and delivery system.

### API

Workflow: https://github.com/Vivek-k24/forgebridge-demo/actions/workflows/api.yml

On a pull request the API workflow:

- installs the Python test environment;
- runs Ruff;
- applies Alembic migrations to PostgreSQL;
- runs API/integration tests;
- builds the API Docker image;
- starts the built container and verifies `/api/v1/health/ready`.

After a successful merge to `main`, the same tested source is published as:

- `ghcr.io/vivek-k24/partgraph-api:<commit-sha>`
- `ghcr.io/vivek-k24/partgraph-api:main`

Package: https://github.com/users/Vivek-k24/packages/container/package/partgraph-api

### Web

Workflow: https://github.com/Vivek-k24/forgebridge-demo/actions/workflows/web.yml

On a pull request the Web workflow:

- installs Node dependencies;
- runs TypeScript type checking;
- performs the production Vite build;
- builds the production Nginx container;
- starts it and verifies an HTTP response.

After a successful merge to `main`, the Web image is published as:

- `ghcr.io/vivek-k24/partgraph-web:<commit-sha>`
- `ghcr.io/vivek-k24/partgraph-web:main`

Package: https://github.com/users/Vivek-k24/packages/container/package/partgraph-web

### Full-stack integration

Workflow: https://github.com/Vivek-k24/forgebridge-demo/actions/workflows/validate.yml

The integration workflow builds the real Compose stack and verifies:

- direct API readiness;
- Web HTTP availability;
- Web-to-API reverse-proxy health.

A future Collector will receive its own workflow and GHCR package when the service actually exists.

The pipeline currently provides continuous integration and tested container delivery. A public full-stack PartGraph URL requires a runtime host for the API and PostgreSQL; GitHub Actions/GHCR are not themselves an application host.

## Merge discipline

For implementation PRs:

1. define scope in a GitHub issue;
2. branch from current `main`;
3. create the PR;
4. wait for all applicable Actions workflows to pass;
5. verify GitHub reports the PR mergeable / ready;
6. merge;
7. allow `main` delivery workflows to publish tested images.

## Performance contract

Normal interactive work should remain comfortably below the 10-second hard blocking boundary. Current quality targets include searchable dropdown p95 under 250 ms, normal API p95 under 1 second, and repair resume p95 under 2 seconds once those workflows exist. Collector work, model training, deployments, and LLM calls never belong on the repair-session critical path.

PartGraph is server-authoritative rather than offline-first. Small transient client caches may improve responsiveness or survive short network interruptions, but private repair truth remains in PostgreSQL and the application does not promise full offline repair operation.

## Current technology baseline

- React 19
- Vite 8
- TypeScript 6
- Nginx 1.29
- Python 3.14
- FastAPI
- SQLAlchemy 2
- Alembic
- PostgreSQL 18
- Docker / Docker Compose
- GitHub Actions / GitHub Container Registry
