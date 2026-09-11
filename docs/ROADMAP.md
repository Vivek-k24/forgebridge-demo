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
| Core software/platform architecture | 78% |
| Security, ownership and data isolation | 86% |
| Error/timeout/degraded resilience | 58% |
| Human RBAC | 42% |
| Canonical automotive data pipeline | 30% |
| Broad canonical automotive knowledge | 8-10% |
| Five-model consumer MVP | 46% |

Major existing strengths:
- authentication and server-side sessions
- private owner state with PostgreSQL row-level security
- Garage and VIN/manual identity foundation
- immutable repair-session event stream and projections
- pause/resume and device edit leases
- repair memory
- requirement/readiness structure
- deterministic procedure engine
- structured error envelope and request IDs
- staging/canonical privilege separation

Major gaps:
- no broad canonical repair library
- generalized cross-repair/downstream dependency model missing
- computer/service-tool boundary can currently be falsely completed
- frontend resume/repair-log device identity bugs
- inventory/readiness dual truth
- event-history pagination
- durable private photo storage
- browser E2E
- true offline repair packs/reconnect flow
- human reviewer/curator/admin RBAC
- canonical evidence-to-repair materialization
- source-code vehicle-data invariant not yet enforced

## 3. Fixed implementation order

### Phase 0 — Consolidate the repository

Goal: one coherent implementation line before new automotive data work.

1. Work from a single consolidation line.
2. Replace stale documentation with `ROADMAP.md` and `BLUEPRINT.md`.
3. Preserve all spreadsheets/JSON/CSV/database data assets.
4. Remove obsolete narrative docs, old architectural instructions and obsolete prototypes.
5. Inventory every Git branch.
6. Selectively port useful code; do not wholesale merge historical experiment branches.
7. Remove code paths that no longer belong to the target architecture.
8. Externalize hard-coded vehicle facts from source/CI into data fixtures.
9. Make supported vehicle selection data-driven.
10. Retire obsolete historical test/acceptance suites while keeping build, lint, dependency-audit and container-smoke CI operational.

Exit gate:
- no useful code remains stranded on an old branch
- no stale documentation competes with the Blueprint
- data assets are preserved
- build/lint/smoke quality gates remain operational
- main can receive one coherent consolidation result

### Phase 1 — Correct existing behavioral defects

1. Make unsupported computer/service-tool boundaries non-completable.
2. Add first-class downstream/cross-repair required-operation relationships.
3. Make completion semantics mechanically honest.
4. Fix Resume Repair device-ID handling.
5. Fix Repair Log device-ID handling.
6. Consume event-history pagination.
7. Correct Garage exact-configuration resolution and verification wording.
8. Reconcile manual session inventory with canonical readiness.
9. Finalize durable private photo storage.
10. Align upload limits with actual hosting limits.
11. Record behaviors that require final regression coverage; do not rebuild the automated test suite until the functional MVP build is complete.

Exit gate:
PartGraph can no longer report a mechanically incomplete or unsupported repair as complete.

### Phase 2 — Restore the resilience contract

1. Preserve the central machine-readable error registry.
2. Formalize error-code ownership by module.
3. Keep request IDs end-to-end.
4. Preserve bounded GET retry behavior.
5. Add authoritative recovery for timed-out writes.
6. Define server-side request/deadline behavior.
7. Standardize degraded/unavailable UI behavior.
8. Implement versioned offline repair packs.
9. Implement offline read-only repair continuity first.
10. If offline writes are enabled, add local event journaling, idempotency, base sequence, conflict detection and reconnect reconciliation.
11. Keep the server authoritative.

Exit gate:
Network loss cannot make PartGraph guess, lose the user's place, or falsely report a mutation.

### Phase 3 — Complete security and RBAC boundaries

1. Preserve `partgraph_app` least-privilege access.
2. Preserve collector staging-only privilege.
3. Preserve transaction-local owner context.
4. Extend FORCE RLS to every new private table.
5. Define human roles:
   - owner/user
   - contributor
   - reviewer
   - curator
   - operator/admin
6. Enforce roles in API services.
7. Enforce database privileges where practical.
8. Do not expose operator workbench functionality before RBAC is present.
9. Keep canonical knowledge shared/read-only to ordinary users.
10. Keep owner state private.
11. Keep candidate acquisition isolated from canonical truth.

Exit gate:
Every read/write/promotion operation has an explicit actor and authorization boundary.

### Phase 4 — Complete the 18-domain canonical schema

Implement the Blueprint domains without vehicle-specific application code:
1. exact vehicle identity
2. systems/assemblies
3. parts/components
4. fitment/applicability
5. interchange/supersession
6. physical relationship graph
7. hardware/fasteners
8. tools/equipment/workspace
9. fluids/materials/consumables
10. specifications/limits
11. repair definitions/operations
12. procedure actions/dependencies
13. triggered downstream operations
14. diagnostics/inspections
15. electrical/sensor/connectors
16. safety/capability boundaries
17. evidence/provenance/conflicts/versioning
18. owner Garage/session/memory/readiness/progress

Exit gate:
An empty database can represent the whole MVP without hard-coded reference-vehicle facts.

### Phase 5 — Clean migration baseline

1. Keep production owner data intact.
2. Build a schema-only future baseline.
3. Move reference/seed vehicle facts to external data fixtures.
4. Test fresh database creation.
5. Test migration against a current production copy.
6. Compare schema and owner-state invariants.
7. Adopt the clean baseline only after proof.
8. Never reset production to simplify migration work.

Exit gate:
Fresh installs and production upgrades follow a generic schema path.

### Phase 6 — Canonical data pipeline

1. source registry
2. source authority policy
3. immutable raw capture
4. extraction/normalization
5. candidate fact generation
6. exact applicability assignment
7. conflict detection
8. reviewer decision
9. verified evidence promotion
10. mechanical claim creation
11. repair-definition materialization
12. versioning/supersession
13. audit trail

Rules:
- missing remains missing
- conflicts remain explicit until resolved
- extraction confidence is not source authority
- retailer data is not sufficient mechanical truth by itself
- old collector thresholds are not inherited automatically
- AI cannot directly publish canonical knowledge

### Phase 7 — Primary end-to-end vehicle

Use the 2009 Honda Civic Hybrid as the deepest first validation configuration.

Build enough canonical coverage to exercise:
- identity
- systems/assemblies
- parts and hardware
- tools
- fluids/materials
- specifications
- repair requirements
- procedures
- readiness
- blockers
- downstream operations
- observations/photos
- pause/resume
- capability boundaries
- completion

Exit gate:
Representative repairs work start-to-finish without vehicle-specific code changes.

### Phase 8 — Five-model reference fleet

Populate the remaining reference fleet through data only.

Rule:
Adding another vehicle may require more data, but must not require a make/model/year/trim `if` statement or a make-specific application service.

Exit gate:
The same source code executes workflows for all five model families.

### Phase 9 — Build the fresh MVP validation suite

Do not revive the historical tests removed during consolidation. Build a new validation suite against the completed Blueprint and the final MVP behavior.

Required gates:
- unit/domain tests
- API tests
- authentication/security tests
- RLS/owner-isolation tests
- migration tests
- production-copy migration
- full-stack integration
- verified-guidance integration
- browser E2E
- randomized acceptance
- reference-fleet acceptance
- offline/degraded behavior
- timeout/ambiguous-write recovery
- downstream-operation semantics
- unsupported computer boundary
- durable photo persistence
- data-free-source-code check
- RBAC authorization tests

### Phase 10 — Production MVP cutover

1. merge only an exact green commit
2. deploy frontend/backend from the same source commit
3. apply only validated schema changes
4. verify health/readiness
5. verify real owner state
6. run production-safe smoke checks
7. do not seed unverified repair data as canonical truth

## 4. Branch consolidation policy

Do not merge historical branches wholesale.

Selective-source branches:
- `partgraph-fix-garage-selects-vin-fallback`
- `partgraph-hosted-parity-hardening`
- `partgraph-reference-fleet-mvp`
- `partgraph-raw-catalog-collectors`
- `partgraph-local-catalog-workbench`

Expected retirement after useful code/data is accounted for:
- old acceptance-harness branches
- old UI/theme branches
- old Pages/deployment probes
- old catalog dashboard branches
- one-time production probes
- CarsXE trim branches
- workbook review branches after datasets are preserved
- temporary `tmp-test-ignore*` branches

No branch is deleted until its unique commits/data are accounted for.

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
