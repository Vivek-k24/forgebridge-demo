# PartGraph MVP Roadmap

Status: Canonical implementation plan  
Architecture authority: `docs/BLUEPRINT.md`

## 1. Definition of done

PartGraph MVP is complete when the same application code can take the selected reference fleet through trustworthy repair workflows using database/data-file knowledge rather than vehicle-specific application logic.

MVP reference fleet:
- 2009 Honda Civic
- 2015 Toyota Camry
- 2018 Ford F-150
- 2020 Subaru Forester
- 2022 Hyundai Tucson

Primary deep test configuration:
- 2009 Honda Civic Hybrid

The names above are validation data. They must not become hard-coded behavior in Python, TypeScript, SQL application logic, CI logic, or UI components.

## 2. Current completion baseline

These percentages are strict MVP completion estimates, not code-volume estimates.

| Area | Completion |
|---|---:|
| Core software/platform architecture | 86% |
| Security, ownership and data isolation | 93% |
| Error/timeout/degraded resilience | 86% |
| Human RBAC | 90% |
| Canonical automotive data pipeline | 75% |
| Broad canonical automotive knowledge | 8-10% |
| Five-model consumer MVP | 50% |

Last exact green implementation candidate before documentation-only status updates:
- `e1f2ceafd7bf8be3fe46f325c3dcbb7c1d4a3505`
- API CI #733: passed, including migration, persisted-history, RBAC, source-authority, Phase 6 lifecycle, adopted-baseline, container-build and readiness-smoke gates
- Web CI #596: passed
- consolidation preview database: `0050_claim_authority_policy`
- production database: intentionally unchanged at `0020_catalog_coverage`

Major existing strengths:
- authentication and server-side sessions
- private owner state with PostgreSQL row-level security
- Garage and VIN/manual identity foundation
- immutable repair-session event stream and projections
- pause/resume and device edit leases
- repair memory
- verified requirement/readiness structure with supplemental owner-added items kept separate
- deterministic procedure engine
- unsupported computer/service-tool boundaries are non-completable
- first-class downstream/cross-repair requirements and mechanically honest completion state
- structured error envelope, request IDs and formal backend error-family ownership
- bounded client retries, server request deadlines and authoritative ambiguous-write recovery
- standardized degraded/unavailable UI state
- versioned, owner-scoped read-only offline repair packs with public-shell-only service-worker caching
- persistent human roles with operator-managed, audited role assignment and a last-admin guardrail
- contributor, reviewer, curator and materializer operations separated by API and PostgreSQL privilege boundaries
- immutable staging/raw evidence, reviewer-gated verified evidence and MechanicalClaim publication
- database-backed source-authority policy with fail-closed publication and conflict resolution
- explicit canonical conflict quarantine, resolution, reopen and claim supersession
- verified-claim-to-repair materialization with canonical version/evidence envelopes and supersession
- fixed adopted schema baseline at migration `0046_pipeline_actor_roles`, with baseline-to-current-head equivalence CI
- production-copy migration proof through the adoption checkpoint without modifying production
- private photo storage implementation with hosted Blob support and local private-volume fallback

Major gaps:
- no broad canonical repair library yet
- real approved-provider ingestion and generic extraction/normalization adapters are not yet complete
- canonical materialization beyond the current repair-definition/requirement/procedure publication path remains incomplete where Phase 6 needs it
- hosted durable photo persistence still needs environment/configuration proof before production cutover
- browser E2E and final offline/degraded regression coverage
- source-code vehicle-data invariant not yet enforced automatically
- reference-fleet canonical data coverage remains Phase 7/8 work

## 3. Fixed implementation order

Task tracking convention:
- `[x]` means the task is implemented and has passed the validation available at that stage.
- `[ ]` means the task is still pending, deferred, or conditional as noted.
- Update the checkbox when each task is completed so this file remains the live record of what is done and what remains.
- A documentation-only status update does not replace the last exact green implementation SHA as the deployment candidate.

### Phase 0 — Consolidate the repository

Goal: one coherent implementation line before new automotive data work.

Status: **Functionally accounted, consolidation line still open.** Historical branch contents have been inventoried and useful generic assets/ideas have been explicitly accounted for. Temporary branches are retained until explicit cleanup approval; branch deletion is not an implementation requirement.

- [x] Work from a single consolidation line.
- [x] Replace stale documentation with `ROADMAP.md` and `BLUEPRINT.md`.
- [x] Preserve all spreadsheets/JSON/CSV/database data assets.
- [x] Remove obsolete narrative docs, old architectural instructions and obsolete prototypes from the active line.
- [x] Inventory every Git branch.
- [x] Selectively port/account for useful code and data from temporary salvage branches; do not wholesale merge historical experiment branches.
- [x] Remove known code paths that no longer belong to the target architecture.
- [x] Externalize known hard-coded vehicle facts from source/CI into data fixtures or database data. Final automated source-code invariant proof remains Phase 9.
- [x] Make supported vehicle selection data-driven.
- [x] Retire obsolete historical test/acceptance suites while keeping build, lint, dependency-audit and container-smoke CI operational.
- [ ] Merge the exact validated consolidation result to `main`. **Production cutover gate; not authorized yet.**

Salvage accounting notes:
- reference-fleet external data assets are preserved
- generic computer/service-tool support-boundary behavior is represented on the active line
- historical workbench code is not promoted wholesale because it bypasses the current human publication boundary
- historical raw/unstructured retailer collector experiments remain reference-only because they conflict with approved-source-first policy
- no temporary Git or Neon branch has been deleted as part of this accounting

Exit gate:
- no useful code remains stranded on an old branch
- no stale documentation competes with the Blueprint
- data assets are preserved
- build/lint/smoke quality gates remain operational
- main can receive one coherent consolidation result

### Phase 1 — Correct existing behavioral defects

Status on `partgraph-mvp-consolidation`:
- core behavioral items are implemented
- private local/hosted photo storage implementation is present; hosted persistence still requires environment-level proof before production cutover
- final behavioral regression remains intentionally deferred to the fresh Phase 9 validation suite

- [x] Make unsupported computer/service-tool boundaries non-completable.
- [x] Add first-class downstream/cross-repair required-operation relationships.
- [x] Make completion semantics mechanically honest.
- [x] Fix Resume Repair device-ID handling.
- [x] Fix Repair Log device-ID handling.
- [x] Consume event-history pagination.
- [x] Correct Garage exact-configuration resolution and verification wording.
- [x] Reconcile manual session inventory with canonical readiness.
- [ ] Finalize durable private photo storage with hosted environment/configuration persistence proof. Implementation exists; proof remains deferred to final validation/cutover.
- [x] Align upload limits with actual hosting limits.
- [ ] Complete fresh final regression coverage for these behaviors. **Deferred to Phase 9.**

Exit gate:
PartGraph can no longer report a mechanically incomplete or unsupported repair as complete.

### Phase 2 — Restore the resilience contract

Status on `partgraph-mvp-consolidation`:
- the functional exit gate is satisfied for the current read-only offline policy
- offline repair pack v1 is generated from server-authoritative resume, readiness and verified guidance state and is versioned by repair-definition version and confirmed session sequence
- private offline pack state is kept in tab-scoped `sessionStorage`; confirmed logout/session invalidation clears it
- the service worker caches only the public application shell and explicitly excludes `/api/` responses; same-tab reload can reopen an already cached repair while the network is unavailable
- final browser/offline/degraded regression proof remains a Phase 9 validation responsibility

- [x] Preserve the central machine-readable error registry.
- [x] Formalize error-code ownership by module.
- [x] Keep request IDs end-to-end.
- [x] Preserve bounded GET retry behavior.
- [x] Add authoritative recovery for timed-out writes.
- [x] Define server-side request/deadline behavior.
- [x] Standardize degraded/unavailable UI behavior.
- [x] Implement versioned offline repair packs.
- [x] Implement offline read-only repair continuity first.
- [ ] If offline writes are enabled, add local event journaling, idempotency, base sequence, conflict detection and reconnect reconciliation. **Conditional; not scheduled for the current read-only MVP.**
- [x] Keep the server authoritative.

Exit gate:
Network loss cannot make PartGraph guess, lose the user's place, or falsely report a mutation.

The functional Phase 2 exit gate is satisfied for the current read-only offline policy. Final browser-level regression proof is deferred to Phase 9 rather than rebuilding the retired test suite during active MVP construction.

### Phase 3 — Complete security and RBAC boundaries

Status: **Functional exit gate satisfied for current operations.** Human authorization and PostgreSQL execution roles now cover the complete implemented evidence-to-repair publication path.

- all five human roles are persistent account states: owner, contributor, reviewer, curator and operator/admin
- contributor submission uses a staging-only `partgraph_contributor` database role
- reviewer decisions and immutable verified-evidence snapshots use `partgraph_reviewer`
- curator MechanicalClaim publication/conflict resolution uses `partgraph_curator`
- canonical repair materialization narrows into dedicated `partgraph_materializer`; the ordinary curator role does not receive broad canonical repair writes
- `partgraph_materializer` can read MechanicalClaim but cannot update it
- claim publication, conflict resolution and materialization coordinate with advisory locks rather than widening claim-table write grants
- source-authority policy is readable by curator but not writable by curator
- ordinary authenticated owner operations retain explicit shared-read/private-owner-state boundaries

- [x] Preserve `partgraph_app` least-privilege access.
- [x] Preserve collector staging-only privilege.
- [x] Preserve transaction-local owner context.
- [x] Extend FORCE RLS to every current private table and require it for every new private table.
- [x] Define human roles: owner/user, contributor, reviewer, curator and operator/admin.
- [x] Enforce roles in current API services.
- [x] Enforce database privileges where practical.
- [x] Separate contributor, reviewer, curator and canonical-materializer execution authority.
- [x] Do not expose operator workbench functionality before RBAC is present.
- [x] Keep canonical knowledge shared/read-only to authenticated ordinary users.
- [x] Keep owner state private.
- [x] Keep candidate acquisition isolated from canonical truth.

Exit gate:
Every implemented read/write/review/promotion/materialization operation has an explicit actor and authorization boundary.

### Phase 4 — Complete the 18-domain canonical schema

Status: **Complete for MVP representational schema.** Broad automotive knowledge population is intentionally separate Phase 6/7/8 work.

Implement the Blueprint domains without vehicle-specific application code:

- [x] exact vehicle identity
- [x] systems/assemblies
- [x] parts/components
- [x] fitment/applicability
- [x] interchange/supersession
- [x] physical relationship graph
- [x] hardware/fasteners
- [x] tools/equipment/workspace
- [x] fluids/materials/consumables
- [x] specifications/limits
- [x] repair definitions/operations
- [x] procedure actions/dependencies
- [x] triggered downstream operations
- [x] diagnostics/inspections
- [x] electrical/sensor/connectors
- [x] safety/capability boundaries
- [x] evidence/provenance/conflicts/versioning
- [x] owner Garage/session/memory/readiness/progress

Exit gate:
An empty database can represent the whole MVP without hard-coded reference-vehicle facts.

### Phase 5 — Clean migration baseline

Status: **Complete.** The adopted baseline is deliberately a fixed checkpoint at `0046_pipeline_actor_roles`; later migrations remain normal forward history rather than regenerating the baseline on every schema change.

- [x] Keep production owner data intact.
- [x] Build and adopt a schema-only future baseline at `0046_pipeline_actor_roles`.
- [x] Move reference/seed vehicle facts to external data fixtures.
- [x] Test fresh database creation.
- [x] Test migration against a current production copy through the adoption checkpoint.
- [x] Compare all pre-existing production data-table row counts and deterministic content digests during production-copy proof.
- [x] Preserve persisted owner-state invariants through `0020_catalog_coverage` to current-head CI upgrades.
- [x] Repair the historical rewritten-0045 case with a forward migration and permanent regression gate.
- [x] Prove the fixed adopted 0046 baseline upgrades to the current head with schema equivalence in CI.
- [x] Never reset production to simplify migration work.

Production-copy adoption proof:
- fresh copy of current production migrated from `0020_catalog_coverage` through `0046_pipeline_actor_roles`
- all 35 pre-existing data tables matched production by row count and deterministic content digest
- production itself remained at `0020_catalog_coverage`
- forward migrations after the adoption checkpoint are exercised by fresh, persisted-history and adopted-baseline upgrade gates in CI

Exit gate:
Fresh installs and production upgrades follow a generic schema path while the fixed baseline remains an immutable checkpoint.

### Phase 6 — Canonical data and provider pipeline

Status: **In progress.** The human evidence-to-claim-to-repair publication spine is implemented and green. Remaining work is primarily generic provider ingestion/extraction and broader canonical publication coverage, followed by actual knowledge population.

- [x] source registry
- [x] source authority policy
- [x] database-backed claim-domain/source/risk authority matrix with fail-closed missing-policy behavior
- [x] provider/connector registry foundation
- [x] immutable raw capture
- [ ] generic extraction/normalization adapters
- [x] candidate fact generation foundation
- [x] exact applicability assignment and enforcement
- [x] conflict detection/quarantine
- [x] reviewer decision
- [x] verified evidence promotion
- [x] mechanical claim creation
- [x] conflict resolution, reopen and claim supersession
- [x] repair-definition/requirement/procedure materialization
- [x] canonical publication versioning/supersession
- [x] canonical record evidence/audit trail
- [x] dedicated least-privilege materializer boundary
- [x] prevent candidate-only source authority from winning curator conflict resolution
- [ ] real approved-provider ingestion/connector operations
- [ ] broader canonical materialization for additional domains where required by the MVP provider pipeline
- [ ] broad canonical repair knowledge population

Current source-authority contract at migration `0050_claim_authority_policy`:
- policy scope is claim domain × source class × risk class
- 70 claim-policy records encode the existing authority matrix as canonical data
- government safety-campaign authority is represented without inventing a false canonical repair domain
- conflict, exact-applicability and explicit-support rules remain product invariants
- missing, malformed or insufficient authority evidence fails closed
- curator can read source-authority policy but cannot rewrite it

MVP provider strategy:
- canonical vehicle and repair data may come from PartGraph database tables and approved backend data files through the same provider/connector boundary
- external URLs or public services may be used only through backend adapters
- the frontend must not contain provider secrets or vehicle-specific source logic
- no real external collector/provider ingestion is activated merely because the generic pipeline exists

Production provider strategy:
- commercial vehicle-data providers, AI providers and manufacturer integrations are registered/configured through an authenticated admin/operator UI
- provider base URLs, capabilities, status and non-secret metadata may be stored in PartGraph configuration tables
- credentials/API keys must be referenced from protected server-side secret storage rather than embedded in application source, frontend bundles or ordinary vehicle-data rows
- each provider adapter writes raw/candidate evidence into the staging plane; external providers never receive direct canonical-publish authority
- AI-provider output remains candidate/explanation input and cannot directly publish canonical automotive truth

Rules:
- missing remains missing
- conflicts remain explicit until resolved
- extraction confidence is not source authority
- retailer/community evidence cannot be elevated by conflict resolution when its authority policy is candidate-only
- old collector thresholds are not inherited automatically
- AI cannot directly publish canonical knowledge

### Phase 7 — Primary end-to-end vehicle

Status: **Pending sufficient Phase 6 generic ingestion/publication coverage.**

Use the 2009 Honda Civic Hybrid as the deepest first validation configuration.

Build enough canonical coverage to exercise:
- [ ] identity
- [ ] systems/assemblies
- [ ] parts and hardware
- [ ] tools
- [ ] fluids/materials
- [ ] specifications
- [ ] repair requirements
- [ ] procedures
- [ ] readiness
- [ ] blockers
- [ ] downstream operations
- [ ] observations/photos
- [ ] pause/resume
- [ ] capability boundaries
- [ ] completion

Exit gate:
Representative repairs work start-to-finish without vehicle-specific code changes.

### Phase 8 — Five-model reference fleet

Status: **Pending Phase 7.**

- [ ] Populate the remaining reference fleet through data only.

Rule:
Adding another vehicle may require more data, but must not require a make/model/year/trim `if` statement or a make-specific application service.

Exit gate:
The same source code executes workflows for all five model families.

### Phase 9 — Build the fresh MVP validation suite

Status: **Pending functional MVP completion.** Existing permanent CI gates remain active; this phase adds the final completed-MVP validation suite rather than reviving historical acceptance infrastructure.

Required gates:
- [ ] unit/domain tests
- [ ] API tests
- [ ] authentication/security tests
- [ ] RLS/owner-isolation tests
- [ ] migration tests
- [ ] production-copy migration
- [ ] full-stack integration
- [ ] verified-guidance integration
- [ ] browser E2E
- [ ] randomized acceptance
- [ ] reference-fleet acceptance
- [ ] offline/degraded behavior
- [ ] timeout/ambiguous-write recovery
- [ ] downstream-operation semantics
- [ ] unsupported computer boundary
- [ ] durable photo persistence
- [ ] data-free-source-code check
- [ ] RBAC authorization tests

### Phase 10 — Production MVP cutover

Status: **Pending Phase 9 and explicit production approval.**

- [ ] merge only an exact green commit
- [ ] deploy frontend/backend from the same source commit
- [ ] apply only validated schema changes
- [ ] verify health/readiness
- [ ] verify real owner state
- [ ] run production-safe smoke checks
- [ ] do not seed unverified repair data as canonical truth

## 4. Branch consolidation policy

Do not merge historical branches wholesale. The following ledger was re-verified against the live repository on 2026-09-12 and salvage accounting was completed before Phase 6 materialization work.

### Keep

- `main` — production/default line
- `partgraph-mvp-consolidation` — active consolidation implementation line

### Keep temporarily as historical references

These branches have been accounted for. They remain present until explicit cleanup approval; their existence does not authorize revival or wholesale merge.

- `partgraph-local-catalog-workbench` — historical generic acquisition/schema ideas; deterministic promotion behavior is superseded by current human publication boundaries
- `partgraph-raw-catalog-collectors` — historical staging/collector ideas; retailer/unstructured source assumptions are superseded by current source-authority policy
- `partgraph-reference-fleet-mvp` — external reference-fleet assets and generic support-boundary history are preserved/accounted for

### Ready to retire when branch cleanup is explicitly approved

These branches are either already fully represented in newer history, are duplicate temporary refs, or contain experiments explicitly rejected/superseded by the current architecture:

- `noop-ignore`
- `partgraph-canada-model-supplement`
- `partgraph-catalog-coverage-dashboard-backend`
- `partgraph-fix-garage-selects-vin-fallback`
- `partgraph-fix-light-card-contrast`
- `partgraph-github-pages-preview`
- `partgraph-hosted-parity-hardening`
- `partgraph-local-acceptance-harness`
- `partgraph-local-acceptance-harness-v2`
- `partgraph-platform-ci-cd`
- `partgraph-production-acceptance-run`
- `partgraph-reference-civic-hybrid-profile`
- `partgraph-repair-session-foundation`
- `partgraph-restore-garage-theme-fix-vin`
- `partgraph-review-gemini-workbook`
- `partgraph-trim-catalog-probe`
- `partgraph-trim-catalog-provider`
- `partgraph-ui-blueprint`
- `partgraph-verify-workbook-exact-selection`
- `tmp-test-ignore2`
- `tmp-test-ignore3`
- `tmp-test-ignore4`
- `tmp-test-ignore5`
- `tmp-test-ignore6`
- `tmp-test-ignore7`

Verification notes:
- old acceptance branches are not revived; Phase 9 builds validation against the final Blueprint
- obsolete CarsXE/probe work remains retired
- Garage/VIN fallback behavior was selectively accounted for; protected persistence remains fail-closed without crypto keys
- hosted-parity storage behavior is represented on the active line, while obsolete hosting assumptions are not
- temporary migration-test Git/Neon branches are not deleted without explicit approval

## 5. No-deviation rule

`docs/BLUEPRINT.md` defines the architecture.  
This file defines implementation sequence.

A bug may change task detail. It does not automatically change architecture.

Any change to:
- ownership model
- canonical-vs-private data boundary
- source authority
- offline authority
- repair completion semantics
- safety/capability boundary
- RBAC model
- deterministic repair execution

requires an explicit architecture decision before implementation.
