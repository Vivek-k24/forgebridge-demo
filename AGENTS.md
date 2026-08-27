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

## Vehicle scope

1. PartGraph is multi-brand. Honda is not a privileged architecture path.
2. Initial market scope is the United States and Canada.
3. Supported model years are 1996 through the current calendar year.
4. The supported-brand registry is maintained in `api/partgraph/vehicle/taxonomy.py`.
5. European premium/luxury brands are outside the current product scope except Volvo, which is explicitly supported.
6. Mainstream, domestic premium, Japanese/Korean premium, and meaningful legacy North-American used-fleet brands may be supported.
7. Brand support is an explicit product decision, not inferred from arbitrary user input.

## Trust rules

1. Never invent OEM numbers, fitment, torque values, fluids, procedures, fastener specifications, interchange, or safety facts.
2. Mechanical truth comes from versioned structured evidence with provenance, not from an LLM.
3. Collector output is staging evidence only and cannot automatically become canonical catalog or service truth.
4. Preserve source identity, source record identity, URL, observed vehicle context, timestamps, raw content hash/payload, extraction method, provenance, confidence, and review state for staging evidence.
5. The collector database role may write only the `catalog_staging` boundary and operational telemetry. It must not write canonical vehicle data or verified catalog evidence.
6. Promotion from staging is an explicit verified operation. Rejected evidence cannot be promoted in place.
7. A promoted `catalog_verified_evidence` row is an immutable verified evidence snapshot; future canonical part/fitment entities still require their own domain validation.
8. Seller data never overrides verified identity or fitment.
9. LLM output may interpret ambiguous language but is never authoritative mechanical truth.
10. Prefer deterministic extraction and lookup for alphanumeric OEM/catalog data.
11. ML training and evaluation are offline. Promote a model only after measurable evaluation against the current baseline.
12. Raw vehicle wording is canonicalized before canonical configuration persistence.
13. Case, punctuation, spacing, safe synonyms, and notation variants must not create duplicate configurations.
14. Compatible partial identities may enrich one canonical record; conflicting facts remain distinct.
15. If more than one canonical configuration is compatible, reject the write as ambiguous instead of guessing.
16. Do not use fuzzy string similarity to merge safety-relevant vehicle variants such as trims, engines, transmissions, or drivetrains.
17. Ordinary user input and future collector output never create shared canonical truth directly.

## Runtime performance rules

1. Catalog collection, training, deployment work, and LLM calls are never on the repair-session resume critical path.
2. Interactive server-backed workflow retrieval targets p95 under 3 seconds.
3. Ten seconds is the hard blocking boundary. The UI must stop blocking and render a useful failure/fallback state rather than spin indefinitely.
4. PostgreSQL is authoritative for private repair state. PartGraph does not promise full offline repair operation.
5. Small transient client caches are acceptable for responsiveness and brief connectivity interruptions, but they are not a second authoritative database.
6. Prefer purpose-built read models/endpoints over frontend request waterfalls.
7. Instrument latency before adding caches or infrastructure.

## User isolation

1. V1 is one owner account with many vehicles.
2. Private data must be user-scoped before `UserVehicle`, VIN, photos, repair sessions, inventory, or fastener state are released.
3. PostgreSQL row-level security is required once private user tables exist.
4. V1 permits one active editing device per repair session; other devices may be read-only until control transfers.
5. Full VIN values must never appear in application logs, analytics, or LLM prompts.

## Repair capability boundary

Guided V1 workflows exclude high-voltage EV/hybrid battery work, airbags/SRS and pyrotechnic pretensioners, immobilizer/security programming, ADAS calibration, structural collision/frame repair, high-voltage inverter/internal battery service, and other procedures explicitly classified as professional/information-only.

## Collector boundary

The collector is separate because crawling is long-running, retry-heavy, externally rate-limited, and failure-prone. It may write only staging data and operational telemetry. It must not directly write canonical PartGraph truth.

The collector is never invoked by a normal user workflow. Do not run production collection from CI or deployment. CI will test the collector against deterministic fixtures when that block exists.

No catalog collection occurs merely because staging tables, migrations, tests, or delivery workflows run.

## Scope discipline

Implement one product block at a time. Keep each block understandable and backed by automated CI/CD checks before merge.

Do not reintroduce retired prototype pages, committed browser catalog dumps, duplicate scripts/tool directories, or infrastructure added only for résumé value.

## Validation

Before merging a block, verify applicable GitHub Actions workflows are green and GitHub reports the PR mergeable/ready. API work must include Ruff, migrations, PostgreSQL tests, container build/smoke; Web work must include TypeScript/build/container smoke; full-stack changes must pass Compose integration.
