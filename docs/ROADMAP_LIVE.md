# PartGraph MVP Roadmap — Live Progress Copy

Status: **Live progress tracker**  
Architecture authority: `docs/BLUEPRINT.md`  
Implementation-sequence source: `docs/ROADMAP.md`  
Maintenance rule: **update this file directly on `main` as soon as a roadmap task is completed. Do not wait for the implementation branch to merge or for its PR to close. Keep the technical tracker and the `Layman Live progress` section synchronized so they describe the same completed, pending, and next work without changing roadmap scope, order, or architecture.**

Last updated: **2026-09-15**

Current exact implementation proof tracked here:
- active implementation branch: `partgraph-mvp-consolidation`
- latest exact green implementation commit: `4a4bcfb764aebffa277b4555afce355f725f006b`
- full API CI: passed (`#786`)
- Web CI: passed (`#649`)
- extraction/provider-ingestion pipeline CI: passed (`#66`)
- canonical publication CI: passed (`#36`)
- reference repair runtime CI: passed (`#12`)
- Vercel consolidation preview: READY on the same commit
- consolidation preview database: `0057_nhtsa_ingest_audit`
- production database: intentionally unchanged at `0020_catalog_coverage`
- PR #84: remains draft/unmerged

The consolidation preview contains 267 reviewed canonical Civic Hybrid part fitments and the first fully canonical repair workflow: `engine-oil-filter-change` version 1, with 8 requirements, 6 ordered procedure actions, `diy_supported` capability, and 14 verified evidence links. The final non-skippable action resets the Maintenance Minder engine-oil-life display to 100% using the vehicle's dashboard controls. A permanent fresh-database runtime gate now reconstructs this approved repair and proves required-readiness blocking, blocker recovery, ordered action progression, pause/resume reorientation, and final mechanical completion.

The active consolidation branch also now contains a staged 2009 Honda Civic Hybrid water-pump repair candidate plus downstream-repair materialization support. The candidate models physical coolant refill/bleed work as the required follow-on operation and explicitly keeps computer/service-tool work out of the executable repair steps. This work is green in CI, but the candidate is still candidate/staging data rather than canonical repair truth, so Phase 7 downstream-operation coverage remains unchecked until human review/publication and end-to-end runtime proof are complete.

This file is intentionally allowed to be newer than `docs/ROADMAP.md` on `main`. It tracks completed work immediately while implementation continues on the consolidation branch.

## Definition of done

PartGraph MVP is complete when the same application code can take the selected reference fleet through trustworthy repair workflows using database/data-file knowledge rather than vehicle-specific application logic.

MVP reference fleet:
- 2009 Honda Civic
- 2015 Toyota Camry
- 2018 Ford F-150
- 2020 Subaru Forester
- 2022 Hyundai Tucson

Primary deep test configuration:
- 2009 Honda Civic Hybrid

Reference vehicles are validation data. They must not become hard-coded behavior in Python, TypeScript, SQL application logic, CI logic, or UI components.

## Task tracking convention

- `[x]` = implemented and validated at the level available for that phase.
- `[ ]` = pending, deferred, conditional, or awaiting an explicit production/cleanup decision.
- A task is checked here immediately after completion, even if the implementation still exists only on `partgraph-mvp-consolidation`.
- A documentation update on `main` does **not** merge implementation code and does **not** authorize production migration, PR merge, provider activation, or branch deletion.

---

## Phase 0 — Consolidate the repository

Status: **Functionally accounted; consolidation line remains open.**

- [x] Work from a single consolidation line.
- [x] Replace stale active-line documentation with the Roadmap and Blueprint.
- [x] Preserve spreadsheets/JSON/CSV/database data assets.
- [x] Remove obsolete narrative docs, architectural instructions, and prototypes from the active line.
- [x] Inventory Git branches.
- [x] Selectively port/account for useful historical code and data without wholesale-merging experiment branches.
- [x] Remove known code paths that do not belong to the target architecture.
- [x] Externalize known hard-coded vehicle facts from source/CI into fixtures or database data.
- [x] Make supported vehicle selection data-driven.
- [x] Retire obsolete historical acceptance infrastructure while preserving build/lint/audit/container-smoke CI.
- [ ] Merge the exact validated consolidation result to `main`. **Production schema/cutover ordering still blocks this.**

Notes:
- historical salvage has been accounted for
- temporary Git and Neon branches remain until explicit cleanup approval
- branch deletion is not implied by phase completion

---

## Phase 1 — Correct existing behavioral defects

Status: **Core behavior implemented; hosted photo persistence proof and final regression remain.**

- [x] Make unsupported computer/service-tool boundaries non-completable.
- [x] Add first-class downstream/cross-repair required-operation relationships.
- [x] Make completion semantics mechanically honest.
- [x] Fix Resume Repair device-ID handling.
- [x] Fix Repair Log device-ID handling.
- [x] Consume event-history pagination.
- [x] Correct Garage exact-configuration resolution and verification wording.
- [x] Reconcile manual session inventory with canonical readiness.
- [ ] Finalize durable private photo storage with hosted environment/configuration persistence proof.
- [x] Align upload limits with actual hosting limits.
- [ ] Complete fresh final regression coverage. **Deferred to Phase 9.**

Exit gate: PartGraph cannot report a mechanically incomplete or unsupported repair as complete.

---

## Phase 2 — Restore the resilience contract

Status: **Functional exit gate satisfied for the current read-only offline policy.**

- [x] Preserve the central machine-readable error registry.
- [x] Formalize error-code ownership by module.
- [x] Keep request IDs end-to-end.
- [x] Preserve bounded GET retry behavior.
- [x] Add authoritative recovery for timed-out writes.
- [x] Define server-side request/deadline behavior.
- [x] Standardize degraded/unavailable UI behavior.
- [x] Implement versioned offline repair packs.
- [x] Implement offline read-only repair continuity.
- [ ] If offline writes are enabled, add local event journaling, idempotency, base sequence, conflict detection, and reconnect reconciliation. **Not scheduled for the current read-only MVP.**
- [x] Keep the server authoritative.

Final browser/offline/degraded regression remains a Phase 9 responsibility.

---

## Phase 3 — Complete security and RBAC boundaries

Status: **Functional exit gate satisfied for current operations.**

- [x] Preserve `partgraph_app` least-privilege access.
- [x] Preserve collector staging-only privilege.
- [x] Preserve transaction-local owner context.
- [x] Extend FORCE RLS to current private tables and require it for new private tables.
- [x] Define owner/user, contributor, reviewer, curator, and operator/admin roles.
- [x] Enforce roles in current API services.
- [x] Enforce database privileges where practical.
- [x] Separate contributor, reviewer, curator, canonical-materializer, and provider-ingestor execution authority.
- [x] Keep operator workbench functionality behind RBAC.
- [x] Keep canonical knowledge shared/read-only to ordinary authenticated users.
- [x] Keep owner state private.
- [x] Keep candidate acquisition isolated from canonical truth.

Implemented execution roles include `partgraph_contributor`, `partgraph_reviewer`, `partgraph_curator`, `partgraph_materializer`, and `partgraph_ingestor`.

---

## Phase 4 — Complete the 18-domain canonical schema

Status: **Complete for MVP representational schema.**

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

Broad automotive data population remains separate Phase 6/7/8 work.

---

## Phase 5 — Clean migration baseline

Status: **Complete.** Adopted baseline remains the fixed checkpoint `0046_pipeline_actor_roles`.

- [x] Keep production owner data intact.
- [x] Build and adopt a schema-only future baseline at `0046_pipeline_actor_roles`.
- [x] Move reference/seed vehicle facts to external data fixtures.
- [x] Test fresh database creation.
- [x] Test migration against a current production copy through the adoption checkpoint.
- [x] Compare pre-existing production tables by row count and deterministic digest.
- [x] Preserve persisted owner-state invariants from `0020_catalog_coverage` through current-head CI upgrades.
- [x] Repair the historical rewritten-0045 case through forward migration and regression testing.
- [x] Prove the adopted 0046 baseline upgrades to current head with schema equivalence.
- [x] Never reset production to simplify migration work.

Production remains at `0020_catalog_coverage` until an explicit production migration decision.

---

## Phase 6 — Canonical data and provider pipeline

Status: **In progress. The generic evidence/provider/publication pipeline is implemented and green; the preview has an enabled NHTSA provider/source binding, 267 canonical Civic part fitments, and the first canonical Civic repair workflow. Broad repair-knowledge population remains.**

Core registry and authority:
- [x] source registry
- [x] source authority policy
- [x] database-backed claim-domain × source-class × risk-class authority matrix
- [x] fail-closed missing/malformed/insufficient authority behavior
- [x] provider/connector registry foundation
- [x] explicit persisted `provider_connection` → `catalog_source` binding

Raw acquisition and extraction:
- [x] immutable raw capture
- [x] candidate-aware staging deduplication so one raw provider record can produce multiple distinct facts
- [x] generic structured extraction/normalization adapter boundary
- [x] deterministic extraction validation for provider enabled state, capability, source approval, and automation permission
- [x] candidate fact generation foundation
- [x] exact vehicle snapshot generation when exact applicability is supplied
- [x] generic extraction database integration test
- [x] extraction pipeline CI gate
- [x] trusted bound-provider execution path using dedicated `partgraph_ingestor` database role
- [x] fail closed on missing or disabled provider/source binding
- [x] prove ingestor can stage candidates but cannot write verified evidence, MechanicalClaims, or canonical repair truth

NHTSA government-source collector:
- [x] deterministic NHTSA recall adapter in `api/partgraph/knowledge/nhtsa.py`
- [x] preserve raw NHTSA response while extracting only selected useful recall fields
- [x] extract campaign/component/issue/consequence/remedy/manufacturer/date/safety flags
- [x] keep year/make/model recall applicability **non-exact** rather than pretending trim/VIN applicability
- [x] ignore unrelated response fields instead of turning them into mechanical truth
- [x] stage NHTSA-derived facts as `pending`
- [x] prove NHTSA staging creates zero verified evidence and zero MechanicalClaims automatically
- [x] NHTSA collector CI safety tests
- [x] configure an approved NHTSA provider/source binding in the isolated consolidation preview
- [ ] prove a live deployed HTTP ingestion invocation through the operator endpoint; configuration alone is not counted as collection

Operator/admin provider controls:
- [x] operator-only source registry list/create/update API
- [x] source license-review and automation controls remain separate gates
- [x] source key/class remain immutable through the operator flow
- [x] operator-only provider/source binding list/create/toggle API
- [x] provider/source pair remains immutable after binding creation
- [x] new bindings are created disabled in the Admin UI
- [x] binding enablement requires provider enabled + source approved + source automation allowed
- [x] source/binding changes are recorded in the operator audit log
- [x] application role may manage source metadata but cannot delete sources or change source-authority policy
- [x] Admin workspace exposes source registration/review/automation and provider/source binding controls
- [x] prove configuration/enablement alone does not create staging records or start collection

Human review/publication spine:
- [x] exact applicability enforcement
- [x] conflict detection/quarantine
- [x] reviewer decision
- [x] verified evidence promotion
- [x] MechanicalClaim creation
- [x] conflict resolution, reopen, and claim supersession
- [x] repair-definition/requirement/procedure materialization
- [x] vehicle-identity claim materialization into an existing exact `VehicleConfiguration` publication envelope without rewriting identity fields
- [x] part-fitment claim materialization using the existing `part_fitments` table with insert-only/fail-closed conflict behavior
- [x] safety-campaign claims remain claim-only and fail closed when canonical materialization is attempted
- [x] canonical publication versioning/supersession
- [x] canonical record evidence/audit trail
- [x] dedicated least-privilege materializer boundary
- [x] permanent canonical-publication CI gate
- [x] prevent candidate-only source authority from winning curator conflict resolution
- [x] publish the first reviewed Honda OEM-service repair through reviewer → curator → materializer authority

Remaining Phase 6 work:
- [x] define and persist an explicit trusted `provider_connection` → `catalog_source` binding
- [x] define the trusted execution role/path that resolves provider configuration and its bound source without widening collector authority
- [ ] complete real-provider live ingestion proof through the deployed operator path
- [x] expose safe provider/source configuration and enable/disable controls through authenticated operator/admin flow where required
- [x] broaden canonical materialization to additional domains where the MVP provider pipeline requires it
- [ ] populate **broad** canonical repair knowledge; one fully reviewed repair is now canonical, but one repair is not broad coverage

Current safety boundary:
- collector/extractor output is candidate data only
- source registration, provider enablement, and binding enablement do **not** start collection by themselves
- external providers have no direct verified/canonical publication authority
- extraction confidence is not source authority
- vehicle identity publication does not rewrite stored identity fields
- canonical part fitment is insert-only through the materializer and conflicting existing rows fail closed
- safety campaigns remain verified claim context with no canonical destination in the current architecture
- missing remains missing
- conflicts remain explicit
- AI cannot directly publish canonical automotive truth
- production provider/collector activation is **not** implied by preview configuration

---

## Phase 7 — Primary end-to-end vehicle

Status: **In progress. The first canonical 2009 Civic Hybrid repair now passes a permanent fresh-database runtime path through readiness, blocker enforcement/recovery, ordered guidance, pause/resume reorientation, and mechanical completion. A water-pump repair candidate is now staged specifically to exercise a required downstream refill/bleed operation, but it is not canonical or runtime-proven yet. Additional repair/domain coverage remains.**

Use the 2009 Honda Civic Hybrid as the deepest first validation configuration.

- [x] identity coverage — exact verified `VehicleConfiguration`
- [ ] systems/assemblies coverage
- [x] parts and hardware coverage — 267 reviewed canonical fitments across cooling, HVAC, intake, brakes, and suspension; repair-specific drain washer also modeled as a requirement
- [x] tools coverage — first canonical repair includes oil-filter wrench and flat-tip screwdriver
- [x] fluids/materials coverage — first canonical repair includes 0W-20 engine oil with verified quantity/unit
- [ ] specifications coverage — torque/capacity are evidence-backed inside the repair workflow, but first-class specification-table coverage is still pending
- [x] repair requirements coverage — first canonical repair has 8 verified requirement uses
- [x] procedures coverage — `engine-oil-filter-change` v1 has 6 ordered, non-skippable actions with evidence; final action resets engine oil life to 100%
- [x] readiness coverage — fresh-database runtime proof loads all 8 requirements, blocks on all 7 required missing items, and allows one recommended item to remain missing
- [x] blockers coverage — the first action cannot complete while its required screwdriver/workspace inputs are missing; setting verified readiness clears the blocker deterministically
- [ ] downstream operations coverage — the oil-change definition has no triggered downstream operation; the staged water-pump candidate now supplies a real physical refill/bleed follow-on case, but it still requires human review/publication and runtime proof before this box can be checked
- [ ] observations/photos coverage
- [x] pause/resume coverage — session pauses after oil drain, preserves the last mechanical checkpoint, and resumes with `Replace the oil filter` as the next verified action
- [x] capability-boundary coverage — first canonical repair is explicitly `diy_supported`; dashboard reset uses physical vehicle controls rather than scan-tool/computer authority
- [x] completion coverage — all 6 supported actions complete in order and the projection reaches `fully_mechanically_complete` with no downstream or unsupported work pending

Current primary-vehicle canonical repair proof:
- repair key: `engine-oil-filter-change`
- repair definition version: `1`
- requirements: `8`
- procedure actions: `6`
- verified evidence/claim links: `14`
- capability: `diy_supported`
- runtime acceptance: `.github/workflows/reference-runtime.yml` / `api/tests/test_reference_repair_runtime.py`
- runtime CI proof: `Reference Repair Runtime CI #12` on `4a4bcfb764aebffa277b4555afce355f725f006b`
- source: Honda OEM service evidence, project-owner reviewed
- repository reference dataset: `api/data/reference/2009_honda_civic_hybrid_repairs_v1/`

Current downstream-operation candidate proof:
- source repair: 2009 Honda Civic Hybrid water-pump replacement candidate
- target follow-on work: physical coolant refill/bleed repair candidate
- downstream repair materialization support: implemented and green
- computer/service-tool executable content: explicitly excluded by regression test
- publication state: candidate/staging only; not canonical yet

Exit gate: representative repairs work start-to-finish without vehicle-specific code changes.

---

## Phase 8 — Five-model reference fleet

Status: **Pending Phase 7.**

- [ ] Populate the remaining reference fleet through data only.

Rule: adding another vehicle may require more data, but must not require make/model/year/trim application-code branches.

---

## Phase 9 — Build the fresh MVP validation suite

Status: **Pending functional MVP completion. Permanent CI gates already created remain active.**

- [ ] unit/domain tests for final MVP behavior
- [ ] API tests for final MVP behavior
- [ ] authentication/security tests
- [ ] RLS/owner-isolation tests
- [ ] migration tests
- [ ] production-copy migration validation
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

Existing permanent CI, including migration history, adopted-baseline equivalence, RBAC, source-authority, extraction, canonical publication, reference-repair runtime, container build, and readiness smoke, remains active and is not discarded while Phase 9 is pending.

---

## Phase 10 — Production MVP cutover

Status: **Pending Phase 9 and explicit production approval.**

- [ ] merge only an exact green implementation commit
- [ ] deploy frontend/backend from the same source commit
- [ ] apply only validated schema changes
- [ ] verify health/readiness
- [ ] verify real owner state
- [ ] run production-safe smoke checks
- [ ] do not seed unverified repair data as canonical truth

---

## Branch and production safeguards

Keep:
- `main` — production/default line; this live roadmap is maintained here immediately
- `partgraph-mvp-consolidation` — active implementation line until production-safe cutover order is satisfied

Historical/temp branches may remain as references. Do not delete Git or Neon branches without explicit approval.

Do not interpret updates to this live roadmap as authorization to:
- merge PR #84
- migrate production
- enable a provider/collector in production
- delete branches
- relax source authority
- bypass human evidence review

## No-deviation rule

`docs/BLUEPRINT.md` defines the architecture. The Roadmap defines implementation sequence. This live copy records implementation progress.

A bug may change task detail. It does not automatically change architecture.

Any change to ownership, canonical/private boundaries, source authority, offline authority, repair completion semantics, safety/capability boundaries, RBAC, or deterministic repair execution requires an explicit architecture decision before implementation.

---

## Layman Live progress

This section says the same thing as the technical tracker above, but in plain English. It does not create new work, change priorities, or change the architecture.

### Where the project stands right now

PartGraph is still being built on the separate `partgraph-mvp-consolidation` branch. The production `main` application and production database have **not** been switched over to this new code. PR #84 is still a draft and has not been merged.

The latest tested implementation commit is `4a4bcfb764aebffa277b4555afce355f725f006b`. The API tests, web tests, data-extraction tests, canonical-publication tests, and reference-repair runtime tests all pass on that exact commit. The Vercel preview for that commit also deployed successfully.

For the 2009 Honda Civic Hybrid, PartGraph currently has 267 reviewed part-fitment records in the preview and one repair that is fully approved and usable from start to finish: the engine-oil-and-filter change. That repair knows what is required before starting, blocks the user when a required item is missing, gives the six repair steps in order, can pause and resume without forgetting where the user stopped, and does not claim completion until the actual mechanical work is finished.

The work immediately after that oil-change proof is the water-pump repair. A **candidate** version of the water-pump repair is now in the branch. It also creates the follow-on coolant refill/bleed work that replacing the water pump requires. This is important because it proves the idea at the heart of PartGraph: replacing one component can create another required operation before the overall repair is truly complete.

That water-pump repair is **not approved canonical data yet**. It is still in the waiting/review area. The code needed to turn a reviewed downstream requirement into canonical repair data has been added and all current tests are green. The repair candidate is also checked so that computer or dealer-service-tool instructions do not quietly get mixed into the physical DIY steps.

### Phase 0 — Put the repository onto one controlled path

Almost everything in this phase is finished. We identified the useful code and data, removed obsolete active paths, stopped relying on hard-coded vehicle facts, and moved ongoing work onto one consolidation branch.

What remains is the final merge to `main`. That will not happen yet because production still needs a safe database-migration and cutover order.

### Phase 1 — Fix behavior that could mislead the user

The important repair-behavior problems are fixed. PartGraph now treats unsupported computer/service-tool work as something the user cannot simply mark complete, understands when one repair creates another required repair, preserves repair history correctly, and keeps readiness and inventory consistent.

Two things remain here: proving that uploaded repair photos stay stored correctly in the hosted environment, and the final full regression test that is intentionally saved for Phase 9.

### Phase 2 — Make the app survive network and timeout problems safely

The current MVP policy is complete: offline use is read-only. A user can keep viewing an already-downloaded repair when the network disappears, but the server remains the final authority for changes.

Offline writing and later synchronization are not part of the current MVP. If that is added later, it will need a separate safe conflict-resolution system.

### Phase 3 — Keep private data and privileged actions separated

This phase is functionally complete. Normal users, contributors, reviewers, curators, data collectors, materializers, and administrators have separate responsibilities and permissions.

A normal user cannot publish automotive truth. A data collector can bring information into the staging area but cannot turn it directly into verified repair knowledge. Owner-specific Garage and repair-session data stays private.

### Phase 4 — Give the database places for every kind of repair knowledge we need

This phase is complete for the MVP structure. The database now has a place for all 18 planned information areas, including exact vehicle identity, parts, fitment, fasteners, tools, fluids, specifications, repairs, ordered steps, required follow-on work, diagnostics, electrical items, safety limits, evidence, conflicts, and the owner's repair state.

This does **not** mean all of those areas are filled with broad automotive data yet. It means PartGraph now has the correct structure to store them without changing application code for every car.

### Phase 5 — Make future database upgrades safe

This phase is complete. We built and tested a clean future database baseline and proved that it can be reached without wiping existing owner data.

The real production database is deliberately still at `0020_catalog_coverage`. We have not migrated production just because the newer preview schema works.

### Phase 6 — Bring outside automotive information in without trusting it automatically

Most of the data pipeline is built. PartGraph can register sources and providers, collect raw data, extract candidate facts, keep source authority rules in the database, detect conflicts, send information through human review, and publish approved information through a restricted canonical-publication path.

The NHTSA recall connector is implemented and safely stages recall information without pretending that a year/make/model recall automatically applies to an exact trim or VIN. An approved NHTSA provider/source connection exists only in the isolated preview.

What still remains in this phase is a real deployed HTTP proof that the operator-triggered NHTSA ingestion path works, and much broader repair-data coverage. One approved oil-change workflow is good proof of the machinery, but it is not broad automotive knowledge.

### Phase 7 — Make the 2009 Honda Civic Hybrid work deeply from beginning to end

This is the phase we are actively working on.

Already working:
- the exact Civic Hybrid configuration is known
- 267 reviewed part fitments are available in the preview
- the oil-change repair has verified requirements, tools, oil, hardware, six ordered steps, readiness checks, blockers, pause/resume behavior, and honest completion
- unsupported computer/service-tool work is kept outside supported DIY completion

Still missing for full Phase 7 coverage:
- broader systems and assembly data
- first-class specification records instead of only evidence inside individual repair steps
- a real end-to-end downstream-repair example
- observations and photo coverage
- additional representative repairs

The current water-pump candidate is intended to close the downstream-repair gap. Replacing the water pump creates required physical coolant refill/bleed work. The next steps are to review and publish that candidate through the normal evidence path, then run it as a real repair session and prove that PartGraph refuses to call the overall job complete until the required follow-on work is also complete. Only after that proof should the downstream-operation checkbox be marked complete.

### Phase 8 — Prove the same design works on five different vehicle models

This has not started yet because the deep Honda proof is not finished.

After Phase 7, the remaining reference vehicles are the 2015 Toyota Camry, 2018 Ford F-150, 2020 Subaru Forester, and 2022 Hyundai Tucson. They must be added through data, not by adding vehicle-specific branches to application code.

### Phase 9 — Run the final MVP test campaign

This phase has not started as a final campaign yet, although many permanent test gates already run on every change.

The final campaign will cover the completed MVP as one whole system: unit tests, API behavior, security, owner isolation, migrations, browser flows, offline behavior, timeout recovery, required downstream repairs, unsupported-computer boundaries, photo persistence, role permissions, randomized acceptance, and all five reference vehicles.

### Phase 10 — Move the finished MVP into production

This has not started and requires explicit production approval.

When that time comes, we will merge only an exact green commit, deploy the frontend and backend from the same source version, apply only migrations already proven safe, verify production health and real owner state, and run production-safe smoke checks. Unverified repair data will never be inserted as canonical truth just to make the production launch look complete.

### Safety rules that remain in force

Updating this progress file does **not** authorize merging PR #84, migrating the production database, turning on data collectors in production, deleting Git or Neon branches, weakening source-authority rules, or skipping human evidence review.

If information is missing, PartGraph must keep it missing instead of guessing. If sources disagree, the conflict stays visible until it is resolved. Candidate or AI-produced information cannot publish itself as canonical automotive truth.

### Exact place to resume work

The implementation should resume from the staged 2009 Honda Civic Hybrid water-pump candidate on `partgraph-mvp-consolidation`.

The next path is: human-review/evidence promotion → canonical publication of the water-pump repair and its required coolant refill/bleed follow-on operation → fresh-database runtime proof → verify that the parent repair remains incomplete while the required follow-on repair is still pending → complete the follow-on repair → verify final mechanical completion.

Until that sequence is actually proven, the Phase 7 downstream-operation checkbox stays unchecked.