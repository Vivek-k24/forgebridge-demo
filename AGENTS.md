# PartGraph Engineering Guide

This file defines durable engineering constraints for PartGraph. GitHub issues and pull requests define the current execution state; `docs/PARTGRAPH_SYSTEM_UML.md` is the living visual architecture map.

## Product center

PartGraph is a stateful AI-assisted automotive repair companion. The private `RepairSession` is the center of the product, not chat, search, a retailer catalog, or an LLM.

The user-facing loop is:

1. **What do I need?** — verified repair definition + Inventory readiness.
2. **How do I do it?** — verified procedure guidance + capability safety.
3. **Where am I now?** — RepairSession + physical repair memory + Resume/reorientation.

Never fabricate records, requirements, steps, parts, blockers, observations, or next actions simply to make a screen look complete.

## Vehicle coverage invariant

1. PartGraph is multi-manufacturer, multi-model, and multi-trim. Honda is a validation case, not a privileged architecture path.
2. Current market scope is the United States and Canada, model years 1996 through the current calendar year, constrained by the supported taxonomy in `api/partgraph/vehicle/taxonomy.py`.
3. Exact `VehicleConfiguration` is the mechanical applicability boundary.
4. Similar names, shared platforms, shared repair keys, or fuzzy matches never authorize cross-configuration repair truth.
5. If vehicle identity or applicability is ambiguous, preserve ambiguity and fail closed instead of guessing.
6. Manufacturer-specific business logic belongs behind an explicit adapter/policy only when the manufacturer actually requires a distinct rule. Generic repair/readiness services stay manufacturer-neutral.

## Current architecture

- `web` — React + TypeScript + Vite; Nginx production container.
- `api` — Python/FastAPI modular monolith.
- PostgreSQL — authoritative canonical and private state.
- `collector` — operator-controlled Python worker for offline/local catalog acquisition; disabled by default in the hosted repair runtime and kept off the interactive repair critical path.
- GitHub Actions — CI/CD and container delivery.
- GitHub Pages — static/read-only current-main frontend preview only.

Do not add Redis, Kafka, Kubernetes, Neo4j, Celery, another database, or a new deployable without a demonstrated requirement. A container boundary is not a reason to create a microservice.

## Canonical truth vs private owner state

Shared canonical truth includes vehicle configurations, verified repair definitions, requirement definitions/uses, and verified mechanical claims.

Private owner state includes `UserVehicle`, VIN material, `RepairSession`, Garage inventory, repair readiness, observations, photos, storage locations, exceptional hardware memory, and session event history.

Canonical truth and private readiness/possession state must never be collapsed into one table or one mutable concept.

## Repair definition model

Canonical relationship:

```text
VehicleConfiguration
  -> RepairDefinition
  -> RepairOperation
  -> RequirementUse
  -> RequirementDefinition
```

The repair-level readiness manifest is a deterministic aggregation over requirement uses for one exact repair definition.

Requirements may represent:

- tool
- equipment
- replacement part
- fluid
- consumable
- hardware
- workspace/setup
- safety prerequisite

### Non-negotiable modeling rule

Do not model `part -> tool` as mechanical truth. A part does not inherently require a socket/wrench/tool; a verified repair operation for an exact vehicle configuration may require it.

Reusable requirements use maximum/simultaneous need semantics; consumed/replacement requirements aggregate explicit quantities. Unknown quantity remains unknown. Conflicting units or fulfillment semantics require explicit canonical review rather than silent conversion.

## RepairSession binding and versioning

1. A session may bind once to an exact verified `RepairDefinition` for its own saved vehicle's canonical configuration.
2. Never infer binding from the free-text session title.
3. The client must not independently supply a different vehicle configuration for binding.
4. Do not silently rebind an existing session.
5. Existing sessions without verified definitions remain valid and can use manual/exception memory.
6. Bound sessions are version-pinned. A later canonical definition may supersede the definition, but an in-progress historical session must remain reconstructable from the definition/evidence it was bound to.
7. Binding metadata is not physical repair progress; do not advance the physical checkpoint merely because canonical repair metadata was attached.

## Inventory/readiness rules

Inventory is the single primary user-facing repair-readiness surface.

1. Verified requirements auto-populate when a session is bound.
2. The user reconciles an aggregated manifest requirement once, even if several operations use it.
3. Readiness states are `have`, `missing`, `ordered`, and `unavailable`.
4. Private session state overrides reusable Garage defaults for that session.
5. Reusable tools/equipment/workspace capability may carry forward into Garage inventory.
6. Consumables, fluids, replacement parts, and repair-specific consumed stock do not automatically become permanent Garage inventory.
7. `reuse_existing` / conditional existing hardware may default from the vehicle only where the verified requirement semantics explicitly support that interpretation.
8. Manual Block 8 inventory is a fallback/exception mechanism, not the primary verified-requirement workflow.
9. Fasteners and Evidence are not primary top-level navigation destinations. Preserve backend capability for exceptional missing/damaged hardware and inline observations/photos.

## Repair-session state rules

1. A `RepairSession` belongs to exactly one user and one `UserVehicle`.
2. Event history is immutable and ordered. Never edit/delete events to make the projection look correct.
3. Current state is rebuildable from immutable history.
4. Physical/readiness mutations require the active edit lease and a stable idempotency key.
5. V1 allows one active editing device; other devices may read until takeover/expiry.
6. Event sequence and idempotency uniqueness must be database-enforced.
7. Pausing/resuming/archiving and domain mutations advance history and projection transactionally.
8. Sessions archive rather than hard-delete once history exists.
9. Resume may report only recorded state.
10. A verified next action requires Block 11 procedure/dependency truth. Until then, explicitly return unavailable rather than asking an LLM to invent a next step.

## Mechanical truth and source authority

Never invent OEM numbers, fitment, torque, fluids, tool sizes, fastener specs, interchange, procedures, safety facts, or compatibility.

Evidence pipeline:

```text
source_record
-> extracted_claim
-> normalized_candidate
-> applicability/conflict validation
-> review/promotion
-> MechanicalClaim
-> RequirementUseEvidence
-> canonical requirement
```

Source authority and extraction confidence are different dimensions.

- Government/open authority: identity, recalls, safety/context within its actual scope.
- OEM service information: highest authority for explicit applicable procedures/specifications/special tools, subject to licensing/terms.
- Licensed OEM-derived structured repair data: scalable option only when product-use/redistribution rights permit.
- OEM parts/licensed parts data: assembly/part identity/applicability/supersession within scope; not automatic procedure/tool truth.
- Industry standards such as ACES/PIES: normalization/exchange semantics, not fitment truth by themselves.
- Retailers/marketplaces: procurement candidates after canonical truth exists.
- Community/forums/videos: discovery/supporting evidence only.

Conflicts never silently overwrite. Unsupported inference stays unverified.

## Collection and corroboration gate

Catalog collection is allowed as an operator-controlled offline/local workflow when it stays outside the interactive repair critical path and preserves provenance. The existence of a seed row or a reachable webpage is not evidence that a configuration is verified.

For ordinary vehicle-configuration identity:

1. A collection batch declares its candidate scope explicitly. Seed candidates are not automatically counted as collected or verified.
2. The collector may gather public source material locally and store raw/cache metadata plus structured source observations.
3. A source contributes a verification vote only when its retrieved content supports the relevant exact configuration signature within that source's actual scope.
4. Three independent matching sources are the normal minimum for automatic canonical configuration verification. A fourth or fifth source may be collected when earlier sources are incomplete, unavailable, or conflicting.
5. Failed, blocked, missing, contradictory, or partial source observations remain visible and do not become agreement.
6. Unresolved conflicts remain unresolved. Do not force a canonical result simply to increase coverage percentage.
7. Configuration-identity corroboration does not automatically verify safety-critical mechanical facts, exact repair procedures, torque values, fluid requirements, fitment, or other domain claims that require stronger/source-specific authority.

Do not:

- run real catalog collection from CI, deployment, page load, or a normal repair session;
- bypass authentication, paywalls, CAPTCHA, robots/access controls, or technical blocking;
- accept new paid-source terms, activate paid credentials, or spend money without explicit approval;
- let a successful HTTP request count as a verification vote without field-level support;
- let an LLM or collector silently overwrite canonical truth merely because it found a plausible value.

Local/operator-controlled public-source collection does not require a separate licensing ceremony before every run. Source terms, access controls, paid activation, redistribution restrictions, and mechanical source authority must still be respected. Collector results enter staging/provenance first; canonical promotion must follow deterministic corroboration/review rules.

## AI boundary

1. AI can explain, rank, summarize, or propose structured observations.
2. AI does not silently change vehicle identity, mechanical truth, repair requirements, procedure truth, readiness, or safety policy.
3. AI is never required for page load, Resume, readiness, or deterministic next-safe-action evaluation.
4. Training/evaluation/deployment is offline from the repair critical path.
5. Prefer deterministic lookup/extraction for alphanumeric OEM/catalog facts.

## Safety/capability boundary

Guided V1 excludes or restricts professional/safety-critical work including high-voltage EV/hybrid battery internals, airbags/SRS/pyrotechnics, immobilizer/security programming, ADAS calibration, structural collision/frame repair guidance, high-voltage inverter/internal battery work, and other explicitly unsupported procedures.

Do not bypass a deterministic capability restriction with an LLM explanation.

## Security and privacy

- Registration: email + username + password; login accepts username or email.
- Argon2id password hashing.
- Opaque server-side session cookie; no browser bearer token storage.
- CSRF + accepted Origin for state-changing browser requests.
- PostgreSQL RLS for private owner tables.
- Full VIN encrypted at rest with AES-GCM and explicit key version.
- Owner-scoped keyed HMAC for VIN duplicate lookup.
- Full VIN never enters normal logs, analytics, exception text, cache keys, or LLM prompts.
- API errors use stable machine-readable codes, user-safe messages, request IDs, retryability, and correct HTTP status.
- Private account/vehicle/repair endpoints use `Cache-Control: no-store`.
- Cross-user IDOR tests are mandatory for private capabilities.

## Performance/reliability contract

- UI acknowledgment target: <100 ms where practical.
- searchable selector p95: <250 ms.
- normal API p95: <1 s.
- RepairSession Resume p95: <2 s.
- hard blocking boundary: 10 s.

Collector/model-training/deployment/LLM work never belongs on the critical repair path. Prefer purpose-built read models over frontend waterfalls. Instrument before adding caches or infrastructure.

Failures must be either structurally prevented, caught by tests, or represented as a visible coded degraded/fallback state. Never turn a timeout or dependency failure into a successful state transition.

## Migration discipline

Persistent developer PostgreSQL volumes are part of the compatibility contract.

1. Never rewrite an Alembic migration that may already be stamped/applied merely to fix a later defect.
2. Add a forward migration and provide a truthful downgrade when feasible.
3. CI must test fresh upgrade, downgrade/re-upgrade, and known persisted-history upgrade paths.
4. Destructive migrations require an explicit data-preservation plan.
5. Never suggest `docker compose down -v` as a routine fix; it intentionally destroys local database data.

## Dependencies/runtime

- Python 3.14 and Node.js 24 are the current runtime majors.
- Direct dependencies are pinned; JavaScript uses committed lockfile + `npm ci`.
- Do not use `--force`, `--legacy-peer-deps`, mixed package managers, or ambient global dependencies to hide incompatibility.
- CI includes `pip check`, `pip-audit`, Ruff, PostgreSQL tests, migration tests, TypeScript/build, npm audit, container smoke, and full Compose integration as applicable.

## UI/product discipline

1. Mobile first, tablet second, desktop supported.
2. Do not expose internal domain tables as navigation merely because they exist.
3. Preserve the simple DIY mental model: requirement/readiness, procedure, current state.
4. No fake/sample mechanical records in production UI.
5. The static GitHub Pages preview is read-only/current-main frontend presentation; it is not the full API runtime.
6. `docs/PARTGRAPH_SYSTEM_UML.md` is the visual architecture reference. Do not create a parallel storyboard/Kanban/Scrum artifact just to track architecture.

## Block discipline and “move forward” execution

Work in coherent runnable blocks. Sub-blocks are allowed when they clarify dependencies/testing/rollback, but they are not a separate project-management system.

When continuing an existing block:

1. Inspect current `main`, branch/PR head, issue scope, migrations, and CI before editing.
2. Continue the current block instead of inventing a new direction.
3. Make routine implementation decisions autonomously.
4. Diagnose and fix red checks; do not merge around them.
5. Preserve architecture/truth/security gates.
6. Local public-source collection may proceed under the corroboration rules above; do not bypass access controls, activate paid sources, spend money, or weaken safety gates without explicit authorization.
7. Update the relevant issue/roadmap/UML when the architecture or completion boundary materially changes.

## Merge/validation discipline

Before merge:

1. final changed head passes every applicable GitHub Actions workflow;
2. GitHub reports mergeable/ready;
3. API changes pass lint, dependency/security checks, migration roundtrip/persisted-history tests, PostgreSQL/RLS/adversarial tests, and container smoke;
4. Web changes pass locked install/audit, TypeScript/build, Nginx/container/security smoke;
5. full-stack changes pass Compose integration;
6. meaningful user-facing behavior receives the required local/runtime verification;
7. red, incomplete, knowingly unverified, or gated work remains unmerged.

After merge, verify `main` delivery and the public preview/runtime surface where applicable.

## Scope discipline

Do not reintroduce retired ForgeBridge/export-platform concepts, stale blueprint navigation, committed browser catalog dumps, duplicate tool directories, or infrastructure added only for appearance. Current `main`, active issues, and the living UML supersede old prototype assumptions.