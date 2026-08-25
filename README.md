# PartGraph

PartGraph is a stateful AI-assisted repair companion that reconstructs the exact vehicle assembly, tracks every part and repair action as you work, and lets you stop for days or weeks and resume from the same step, same part, and same fastener.

## Block 1 — runtime foundation

This block establishes the interactive runtime only:

```text
web (React/TypeScript)
        ↓
api (Python/FastAPI modular monolith)
        ↓
PostgreSQL
```

The future catalog collector is a separate backend service because crawling is long-running and failure-prone. It is intentionally not implemented or containerized yet; no collection happens in this block.

At the system level PartGraph will therefore have two backend deployables: the interactive API modular monolith and the collector service. The web client and PostgreSQL are separate runtime components, not domain microservices.

## Run locally

Requirements: Docker Desktop with Docker Compose.

```bash
docker compose up --build
```

Open:

- Web: `http://localhost:5173`
- API readiness: `http://localhost:8000/api/v1/health/ready`
- API docs: `http://localhost:8000/docs`

Expected web state: **Interactive runtime ready** with measured HTTP round-trip and PostgreSQL query latency.

Stop with:

```bash
docker compose down
```

The PostgreSQL volume is retained between runs.

## Performance contract

The normal interactive workflow target is p95 under 3 seconds. Ten seconds is a hard blocking boundary, not a target. Collector work, model training, deployments, and LLM calls must never be on the repair-session critical path.

## Current technology baseline

- React 19.2
- Vite 8
- TypeScript 6
- Python 3.14
- FastAPI
- PostgreSQL 18

Production deployment remains disabled while the rebuild is reviewed block by block.
