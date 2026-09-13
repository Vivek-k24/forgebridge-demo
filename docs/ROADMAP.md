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
| Core software/platform architecture | 81% |
| Security, ownership and data isolation | 89% |
| Error/timeout/degraded resilience | 86% |
| Human RBAC | 65% |
| Canonical automotive data pipeline | 30% |
| Broad canonical automotive knowledge | 8-10% |
| Five-model consumer MVP | 48% |

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
- reviewer-gated staging review with a separate least-privilege PostgreSQL reviewer role
- verified evidence promotion remains distinct from canonical automotive publication
- staging/canonical privilege separation
- private photo storage implementation with hosted Blob support and local private-volume fallback

Major gaps:
- no broad canonical repair library
- hosted durable photo persistence still needs environment/configuration proof before production cutover
- browser E2E and final offline/degraded regression coverage
- contributor submission and curator publication/conflict-resolution actions do not exist yet because their Phase 6 pipeline operations do not exist yet
- canonical evidence-to-repair materialization
- source-code vehicle-data invariant not yet enforced automatically
- clean migration baseline and production-copy migration proof remain outstanding

## 3. Fixed implementation order

Task tracking convention:
- `[x]` means the task is implemented and has passed the validation available at that stage.
- `[ ]` means the task is still pending, deferred, or conditional as noted.
- Update the checkbox when each task is completed so this file remains the live record of what is done and what remains.
- A documentation-only status update does not replace the last exact green implementation SHA as the deployment candidate.

### Phase 0 — Consolidate the repository

Goal: one coherent implementation line before new automotive data work.

Status: **In progress.** The active line is consolidated, but the remaining temporary salvage branches still require final accounting before the exit gate is closed.

- [x] Work from a single consolidation line.
- [x] Replace stale documentation with `ROADMAP.md` and `BLUEPRINT.md`.
- [x] Preserve all spreadsheets/JSON/CSV/database data assets.
- [x] Remove obsolete narrative docs, old architectural instructions and obsolete prototypes from the active line.
- [x] Inventory every Git branch.
- [ ] Selectively port/account for useful code and data from the remaining temporary salvage branches; do not wholesale merge historical experiment branches. **Active.**
- [x] Remove known code paths that no longer belong to the target architecture.
- [x] Externalize known hard-coded vehicle facts from source/CI into data fixtures or database data. Final automated source-code invariant proof remains Phase 9.
- [x] Make supported vehicle selection data-driven.
- [x] Retire obsolete historical test/acceptance suites while keeping build, lint, dependency-audit and container-smoke CI operational.

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

Status on `partgraph-mvp-consolidation`:
- all five human roles are persistent account states: owner, contributor, reviewer, curator and operator/admin
- reusable API role dependencies exist for contributor-capable, reviewer, curator and operator operations
- operator/admin routes use explicit operator authorization rather than UI hiding
- operator/admin can list accounts and assign human roles through audited API/UI controls; the last active operator/admin cannot be demoted
- evidence review is restricted to reviewer, curator or operator/admin accounts and runs under a separate `partgraph_reviewer` PostgreSQL role
- the reviewer database role can read staging evidence, update only review fields and create immutable verified-evidence snapshots; it has no canonical write authority
- verification currently stops at `CatalogVerifiedEvidence`; it cannot publish `MechanicalClaim`, vehicle truth, repair definitions, operations or requirements
- contributor candidate-submission and curator publication/conflict-resolution endpoints are intentionally not fabricated ahead of the Phase 6 pipeline operations they would authorize
- shared canonical and vehicle reads now use an explicit authenticated ordinary-user boundary; reviewer-only staging/reconciliation/coverage reads narrow the transaction to `partgraph_reviewer`
- migration `0032_shared_read_privileges` grants only the missing shared read privileges and CI exercises the real PostgreSQL role boundary
- API CI and Web CI passed for `a28a5372b310fe11e696789c7840f54170aca5ed`, including migration `0032`, live PostgreSQL RBAC tests and container smoke

- [x] Preserve `partgraph_app` least-privilege access.
- [x] Preserve collector staging-only privilege.
- [x] Preserve transaction-local owner context.
- [x] Extend FORCE RLS to every current private table and require it for every new private table.
- [x] Define human roles: owner/user, contributor, reviewer, curator and operator/admin.
- [x] Enforce roles in current API services.
- [x] Enforce database privileges where practical.
- [x] Do not expose operator workbench functionality before RBAC is present.
- [x] Keep canonical knowledge shared/read-only to authenticated ordinary users.
- [x] Keep owner state private.
- [x] Keep candidate acquisition isolated from canonical truth.

Exit gate:
Every read/write/promotion operation has an explicit actor and authorization boundary.

The functional Phase 3 exit gate is satisfied for operations that currently exist. Contributor candidate-submission and curator publication/conflict-resolution authorization will be added with the corresponding Phase 6 operations rather than fabricating unused write paths early.

### Phase 4 — Complete the 18-domain canonical schema

Status: **In progress.** Domains 1-5 are complete. Exact identity was audited against the existing canonical/private VIN model; migration `0033_vehicle_structure` adds the system/assembly hierarchy; migration `0034_parts_components` adds canonical component definitions, manufacturer part identities and component/part position roles; migration `0035_part_fitment` adds exact-configuration applicability, exclusions and qualifiers; migration `0036_part_interchange` adds directed supersession/service-replacement edges and valid interchange identity. The Domain 5 implementation passed API CI, Web CI, preview migration and least-privilege database checks on `490c1aaf0a406b8f7e4b534c0d9c3f7e0cb61bfb`.

Implement the Blueprint domains without vehicle-specific application code:

- [x] exact vehicle identity
- [x] systems/assemblies
- [x] parts/components
- [x] fitment/applicability
- [x] interchange/supersession
- [ ] physical relationship graph
- [ ] hardware/fasteners
- [ ] tools/equipment/workspace
- [ ] fluids/materials/consumables
- [ ] specifications/limits
- [ ] repair definitions/operations
- [ ] procedure actions/dependencies
- [ ] triggered downstream operations
- [ ] diagnostics/inspections
- [ ] electrical/sensor/connectors
- [ ] safety/capability boundaries
- [ ] evidence/provenance/conflicts/versioning
- [ ] owner Garage/session/memory/readiness/progress

Exit gate:
An empty database can represent the whole MVP without hard-coded reference-vehicle facts.

### Phase 5 — Clean migration baseline

Status: **Pending Phase 4.**

- [ ] Keep production owner data intact.
- [ ] Build a schema-only future baseline.
- [ ] Move reference/seed vehicle facts to external data fixtures.
- [ ] Test fresh database creation.
- [ ] Test migration against a current production copy.
- [ ] Compare schema and owner-state invariants.
- [ ] Adopt the clean baseline only after proof.
- [ ] Never reset production to simplify migration work.

Exit gate:
Fresh installs and production upgrades follow a generic schema path.

### Phase 6 — Canonical data and provider pipeline

Status: **Pending Phase 5.** Existing staging/provider/evidence foundations will be audited when this phase begins; they are not pre-checked as complete here.

- [ ] source registry
- [ ] source authority policy
- [ ] provider/connector registry
- [ ] immutable raw capture
- [ ] extraction/normalization
- [ ] candidate fact generation
- [ ] exact applicability assignment
- [ ] conflict detection
- [ ] reviewer decision
- [ ] verified evidence promotion
- [ ] mechanical claim creation
- [ ] repair-definition materialization
- [ ] versioning/supersession
- [ ] audit trail

MVP provider strategy:
- canonical vehicle and repair data may come from PartGraph database tables and approved backend data files through the same provider/connector boundary
- external URLs or public services may be used only through backend adapters
- the frontend must not contain provider secrets or vehicle-specific source logic

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
- retailer data is not sufficient mechanical truth by itself
- old collector thresholds are not inherited automatically
- AI cannot directly publish canonical knowledge

### Phase 7 — Primary end-to-end vehicle

Status: **Pending Phase 6.**

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

Status: **Pending functional MVP completion.**

Do not revive the historical tests removed during consolidation. Build a new validation suite against the completed Blueprint and the final MVP behavior.

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

Status: **Pending Phase 9.**

- [ ] merge only an exact green commit
- [ ] deploy frontend/backend from the same source commit
- [ ] apply only validated schema changes
- [ ] verify health/readiness
- [ ] verify real owner state
- [ ] run production-safe smoke checks
- [ ] do not seed unverified repair data as canonical truth

## 4. Branch consolidation policy

Do not merge historical branches wholesale. The following ledger was re-verified against the live repository on 2026-09-12.

### Keep

- `main` — production/default line
- `partgraph-mvp-consolidation` — active consolidation implementation line

### Keep temporarily for selective salvage

- `partgraph-local-catalog-workbench` — newest surviving workbench/identity-catalog line; useful generic acquisition/schema ideas must be reviewed selectively
- `partgraph-raw-catalog-collectors` — generic staging/collector ideas must be reviewed selectively; old source-policy assumptions are not automatically inherited
- `partgraph-reference-fleet-mvp` — preserve external reference-fleet data and generic support-boundary ideas before retirement

### Ready to retire

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
- `partgraph-local-acceptance-harness`, `partgraph-local-acceptance-harness-v2`, `partgraph-fix-light-card-contrast`, `partgraph-github-pages-preview`, `partgraph-platform-ci-cd`, `partgraph-reference-civic-hybrid-profile`, `partgraph-repair-session-foundation`, and `partgraph-verify-workbook-exact-selection` are zero commits ahead of current `main` at the time verified.
- `noop-ignore` and all `tmp-test-ignore2` through `tmp-test-ignore7` resolve to the same old workbench commit; that commit is fully contained in `partgraph-local-catalog-workbench`, which is retained.
- `partgraph-catalog-coverage-dashboard-backend` contains catalog-coverage files already represented on the active implementation line.
- `partgraph-production-acceptance-run` is obsolete acceptance-test infrastructure and is retired under the decision to rebuild tests after the functional MVP.
- `partgraph-review-gemini-workbook` contains only an obsolete review workflow; the workbook/data asset is already preserved independently.
- `partgraph-trim-catalog-provider` and its probe line are retired with the CarsXE path.
- the Garage/VIN fallback branch has been selectively accounted for: verified canonical matching and decode-only fallback are retained in consolidation; the path that would save VIN-derived identity without protected VIN storage is intentionally not adopted because protected persistence must fail closed without crypto keys.
- `partgraph-hosted-parity-hardening` has been selectively accounted for: its private Vercel Blob/local-volume storage implementation is present byte-for-byte in consolidation; its old GitHub Pages root redirect is intentionally superseded; its old hosted-photo test is not revived because the final test suite is intentionally rebuilt in Phase 9; and its old web API-base fallback is superseded by the current explicit/same-origin configuration.

No branch in the temporary-salvage set is retired until its useful generic code/data is explicitly accounted for.

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
