# PartGraph Engineering Guide

## Product

PartGraph maintains a trustworthy digital representation of a physical repair as it changes over time. It must know what the exact vehicle assembly should contain, what the user has observed, what has already changed during the repair, and what can safely happen next.

> PartGraph is a stateful AI-assisted repair companion that reconstructs the exact vehicle assembly, tracks every part and repair action as work progresses, and lets a repair resume from the same physical state after a pause.

The private `RepairSession` is the product center. Vehicle identification is an entry point; chat, AI, catalog ingestion, and diagnosis are supporting capabilities rather than the primary state container.

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
18. VIN decoders and other external identity providers produce observations, not canonical truth. Cache their observation if useful, but re-resolve it against current canonical data rather than freezing a provider result as authority.

## Runtime performance rules

1. Catalog collection, training, deployment work, and LLM calls are never on the repair-session resume critical path.
2. Interactive server-backed workflow retrieval targets p95 under 3 seconds; the purpose-built repair-session Resume read targets p95 under 2 seconds.
3. Ten seconds is the hard blocking boundary. The UI must stop blocking and render a useful failure/fallback state rather than spin indefinitely.
4. PostgreSQL is authoritative for private repair state. PartGraph does not promise full offline repair operation.
5. Small transient client caches are acceptable for responsiveness and brief connectivity interruptions, but they are not a second authoritative database.
6. Prefer purpose-built read models/endpoints over frontend request waterfalls.
7. Instrument latency before adding caches or infrastructure.

## User isolation

1. V1 is one owner account with many vehicles.
2. Sign-up uses email, username, and password. Sign-in accepts username or email.
3. Usernames are case-insensitive, 3–32 characters, and contain only ASCII letters, digits, or underscore.
4. Private data must be user-scoped before `UserVehicle`, VIN, photos, repair sessions, inventory, or fastener state are released.
5. PostgreSQL row-level security is required once private user tables exist.
6. V1 permits one active editing device per repair session; other devices may be read-only until control transfers.
7. Full VIN values must never appear in application logs, analytics, exception messages, cache keys, or LLM prompts.
8. Full VIN values stored by PartGraph require authenticated encryption with explicit key versioning; encryption keys come only from runtime secret configuration.
9. Deterministic VIN duplicate detection uses a keyed, owner-scoped fingerprint rather than plaintext or a bare unsalted hash. Different owners must not be able to infer one another's VIN presence from duplicate behavior.
10. Normal API/UI representations expose a masked VIN only. Decryption is not part of ordinary list/read rendering.
11. Passwords, password hashes, raw session tokens, CSRF material, VIN cryptographic keys, and other secrets must never be logged.

## Repair-session state rules

1. A `RepairSession` belongs to exactly one user-owned `UserVehicle`. It is private and covered by the same application user filter plus PostgreSQL RLS defense in depth.
2. Repair-session event history is append-only from the application role. Never update or delete an event to make current state look correct.
3. Current repair state is a disposable projection/read model. If it is missing or stale, rebuild it deterministically from the immutable ordered event history.
4. Every physical-state mutation requires the active edit lease for that session and a stable idempotency key. Viewing/resume reads do not require editing control.
5. V1 has one active editing device per repair session. A second device may read; mutation is rejected until the lease expires or the user explicitly takes over the session.
6. Event sequence and idempotency uniqueness are database-enforced. Concurrent requests must serialize or fail with a deterministic coded conflict rather than depend on Python timing.
7. Pausing, resuming, archiving, and future repair-state transitions append events first and advance the projection transactionally in the same database transaction.
8. Repair sessions are archived rather than hard-deleted once history exists.
9. A Resume response may report only state PartGraph has actually recorded. Never populate missing parts, fasteners, observations, blockers, plan steps, or actions just to make the UI look complete.
10. A “next safe action” requires verified repair-plan/dependency truth plus current physical state. Until that domain exists, the product must explicitly say the action is unavailable rather than infer one from an LLM or a generic procedure.

## Reliability and error contract

1. A failure class must be prevented structurally, caught in CI, or produce a visible coded fallback/degraded state. Silent failure is not acceptable.
2. Every non-success API response must use the versioned PartGraph error envelope with a stable `code`, user-safe `message`, `request_id`, `retryable` flag, and appropriate HTTP status.
3. Every warning/error log entry must carry a stable code and correlation/request ID where a request exists. Never log request bodies merely to diagnose an error.
4. API paths, schemas, and API-version headers are contracts. Client/API version mismatch must fail visibly instead of being silently deserialized.
5. Validate user input independently at browser, API, and database boundaries where integrity matters. Browser validation is UX, never the security boundary.
6. Bound payload/file sizes before expensive parsing, hashing, AI, or storage work.
7. Use UTC-aware server timestamps and explicit wire formats. Do not depend on machine-local timezone or locale.
8. Automatic retries must be bounded and limited to safe/idempotent work unless an explicit idempotency key/protocol exists for the state-changing action.
9. A network timeout or unavailable dependency may not be converted into a successful state transition. Preserve known server-authoritative state and show degraded/retry UX.
10. Cache use requires user/tenant scope, version/invalidation semantics, TTL, and authoritative fallback before adoption. A cache must never become an undocumented second database.
11. Identity creation, event/state transitions, deduplication, and other concurrent writes require race-condition tests and database-enforced invariants.
12. CORS, CSRF, cookie flags, reverse-proxy behavior, security headers, and Content Security Policy must be integration-tested whenever those boundaries change.
13. New capabilities such as uploads, WebSockets, or webhooks require their own size/handshake/signature/replay/error tests before they ship; do not add placeholder infrastructure merely to satisfy this rule.

## Dependency and runtime compatibility

1. Supported runtimes are explicit. Current baseline is Python 3.14 and Node.js 24; a runtime-major change is an intentional migration, not ambient CI drift.
2. Direct dependencies use exact versions. JavaScript transitive dependencies use a committed lockfile and `npm ci`.
3. Use one package manager/lock strategy per deployable. Do not mix npm/yarn/pnpm or Poetry/Pipenv state.
4. CI runs dependency-integrity and security checks (`pip check`, `pip-audit`, `npm audit`) and type/build/container smoke tests.
5. React and React-DOM versions must match. Vite/plugins, TypeScript/type packages, and framework peers must resolve without `--force` or `--legacy-peer-deps`.
6. Reversible Alembic migrations must be downgrade/upgrade tested in CI before merge. Destructive migrations require an explicit data-preservation/migration plan instead of a fake rollback.
7. Production containers must not depend on global developer packages or mutable host environments.
8. Native/C-extension or multi-architecture support must be tested on every claimed architecture before ARM64/x86 portability is stated.
9. Do not accept a dependency warning as harmless by default. Resolve it, pin around it with documented evidence, or fail the build.

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

Before merging a block, verify applicable GitHub Actions workflows are green and GitHub reports the PR mergeable/ready. API work must include Ruff, dependency integrity/security checks, reversible migration checks, PostgreSQL tests, container build/smoke; Web work must include locked dependency install, dependency audit, TypeScript/build/container smoke; full-stack changes must pass Compose integration and relevant adversarial user-flow checks.
