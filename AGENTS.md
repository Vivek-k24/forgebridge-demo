# PartGraph Engineering Guide

## Product

PartGraph maintains a trustworthy digital representation of a physical repair as it changes over time. It must know what the exact vehicle assembly should contain, what the user has observed, what has already changed during the repair, and what can safely happen next.

> PartGraph is a stateful AI-assisted repair companion that reconstructs the exact vehicle assembly, tracks every part and repair action as you work, and lets you stop for days or weeks and resume from the same step, same part, and same fastener.

## System architecture

PartGraph is distributed at the top-level service boundary but deliberately not microservice-heavy.

- `web` — React + TypeScript client.
- `api` — Python/FastAPI deployable containing the modular monolith.
- `collector` — separate Python ingestion service when implemented.
- PostgreSQL — shared physical database infrastructure with explicit logical ownership boundaries.

Inside `api`, domain modules remain in-process until measured scale or team ownership justifies extraction. A container is a deployment unit, not a reason to create a microservice.

Do not create an empty collector implementation. Add its container only when the real ingestion capability is built.

## Trust rules

1. Never invent OEM numbers, fitment, torque values, fluids, procedures, fastener specifications, interchange, or safety facts.
2. Mechanical truth comes from versioned structured evidence with provenance, not from an LLM.
3. Collector output is staging evidence only and cannot automatically become canonical catalog or service truth.
4. The collector preserves source, URL, observed vehicle configuration, timestamp, extraction method, and review status.
5. Seller data never overrides verified identity or fitment.
6. LLM output may interpret ambiguous language but is never authoritative mechanical truth.
7. Prefer deterministic extraction and lookup for alphanumeric OEM/catalog data.
8. ML training and evaluation are offline. Promote a model only after measurable evaluation against the current baseline.
9. A manually entered vehicle configuration remains `unverified` until an evidence-backed process verifies it. Normalized deduplication is not verification.
10. Vehicle configuration identity records are not silently rewritten. Reconciliation or correction must remain explicit and auditable.

## Runtime performance rules

1. Catalog collection, training, deployment work, and LLM calls are never on the repair-session resume critical path.
2. Interactive server-backed workflow retrieval targets p95 under 3 seconds.
3. Ten seconds is the hard blocking boundary. The UI must stop blocking and render useful cached/partial verified state.
4. Repair state is designed to become local-first for poor garage connectivity.
5. Prefer purpose-built read models/endpoints over frontend request waterfalls.
6. Instrument latency before adding caches or infrastructure.

## Collector boundary

The collector is separate because crawling is long-running, retry-heavy, externally rate-limited, and failure-prone. It may write only staging data and operational telemetry. It must not directly write canonical PartGraph truth.

The collector is never invoked by a normal user workflow. Do not run production collection from CI or deployment. CI will test the collector against deterministic fixtures when that block exists.

## Scope discipline

Implement one product block at a time. Every block must be runnable locally and understandable before merge.

Do not reintroduce retired prototype pages, committed browser catalog dumps, duplicate scripts/tool directories, or infrastructure added only for résumé value.

## Validation

Before presenting a block as ready for review, verify API lint/tests against PostgreSQL, database migrations, web typecheck/build, and Docker Compose configuration validation.
