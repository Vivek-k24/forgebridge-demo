# PartGraph Engineering Guide

## Product

PartGraph maintains a trustworthy digital representation of a physical repair as it changes over time. It must know what the exact vehicle assembly should contain, what the user has observed, what has already changed during the repair, and what can safely happen next.

Product position:

> PartGraph is a stateful AI-assisted repair companion that reconstructs the exact vehicle assembly, tracks every part and repair action as you work, and lets you stop for days or weeks and resume from the same step, same part, and same fastener.

## Rebuild architecture

Use three application boundaries:

1. `web` — React + TypeScript.
2. `api` — Python modular monolith.
3. `collector` — isolated Python ingestion service.

Do not split the API domain into independently deployed microservices without measured operational need.

## Trust rules

1. Never invent OEM numbers, fitment, torque values, fluids, procedures, fastener specifications, interchange, or safety facts.
2. Mechanical truth must come from versioned structured evidence with provenance, not from an LLM.
3. Collector output is staging evidence only. It cannot automatically become canonical catalog or service truth.
4. The collector must preserve source, URL, observed vehicle configuration, timestamp, extraction method, and review status.
5. Seller data never overrides verified identity or fitment.
6. LLM output may help interpret ambiguous language, but it is never authoritative mechanical truth.
7. Deterministic extraction and lookup are preferred for alphanumeric OEM/catalog data.
8. Training and ML evaluation are offline operations. A new model is promoted only after measurable evaluation against the current baseline.

## Runtime performance rules

1. Catalog collection, model training, deployment work, and LLM calls are never on the repair-session resume critical path.
2. Interactive server-backed workflow retrieval targets p95 under 3 seconds.
3. Ten seconds is the hard blocking boundary. The UI must render useful verified cached/partial state instead of waiting indefinitely.
4. Repair state is designed to become local-first so interruption/resume can work even with poor garage connectivity.
5. Prefer one purpose-built resume/read endpoint over sequential frontend waterfalls.

## Collector boundary

The collector is the one deliberate service boundary because crawling is long-running, retry-heavy, externally rate-limited, and failure-prone. It may write staging data and operational telemetry. It must not directly write canonical PartGraph truth.

Do not run production collection from CI or deployment. CI tests collectors against deterministic fixtures.

## Scope discipline

Implement one product block at a time. Do not combine unrelated capabilities because they are convenient to code together. Every block must be runnable locally and understandable before merge.

Do not reintroduce retired prototype pages, hardcoded repair graphs, generated catalog JSON committed for browser consumption, duplicate scripts/tool directories, or architecture added only for résumé value.

## Validation

Before presenting a block as ready for local review, run or verify CI for:

```bash
npm run lint
npm run build
```

When Python services are introduced, add their unit/type/lint checks to the same validation contract.
