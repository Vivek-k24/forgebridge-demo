# PartGraph MVP Roadmap — Live Progress Copy

Status: **Live progress tracker**  
Architecture authority: `docs/BLUEPRINT.md`  
Implementation-sequence source: `docs/ROADMAP.md`  
Maintenance rule: **update this file directly on `main` as soon as a roadmap task is completed. Do not wait for the implementation branch to merge or for its PR to close. Keep the technical tracker and the `Layman Live progress` section synchronized so they describe the same completed, pending, and next work without changing roadmap scope, order, or architecture.**

Last updated: **2026-09-15**

Current exact implementation proof tracked here:
- active implementation branch: `partgraph-mvp-consolidation`
- latest exact green implementation/data commit: `1cbd46da63285683ef919b0dd917eff6ffad7142`
- full API CI: passed (`#793`)
- Web CI: passed (`#656`)
- extraction/provider-ingestion pipeline CI: passed (`#78`)
- canonical publication CI: passed (`#43`)
- reference repair runtime CI: passed (`#23`)
- Vercel consolidation preview: READY on the same commit (`dpl_CnPvQFAF6pYPxFCrZ4fmJrw82qBv`)
- consolidation preview database schema: `0058_downstream_materializer`
- production database: intentionally unchanged at `0020_catalog_coverage`
- PR #84: remains draft/unmerged

The long-lived consolidation preview contains 267 reviewed canonical Civic Hybrid part fitments and the verified `engine-oil-filter-change` repair definition. The approved repository reference dataset now also contains `engine-water-pump-replacement` and its required supported follow-on repair, `cooling-system-refill-air-bleed`. Those two repairs are canonically materialized through the normal verified-evidence → MechanicalClaim → restricted materializer path inside the permanent fresh-database runtime gate. They have not been silently seeded into the long-lived preview database; the preview's persistent canonical repair row remains the oil-change definition.

The water-pump path closes the primary-vehicle downstream-operation proof. Completing `install-water-pump` activates a supported coolant refill/air-bleed requirement. The parent repair remains `downstream_required_pending`; starting the linked repair does not satisfy it; attempting to satisfy it before the linked repair is mechanically complete fails closed; and only after the linked physical refill/bleed workflow is complete can the parent repair resolve to `fully_mechanically_complete`. Computer/service-tool work remains excluded from this physical follow-on repair.

Charm.li service-manual mirror evidence for this exact approved MVP reference path is classified `licensed_oem_derived`, project-owner reviewed on 2026-09-15, and approved for manual evidence use only. `automation_allowed` remains `false`.

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

Status: **In progress. The generic evidence/provider/publication pipeline is implemented and green. The preview has an enabled NHTSA provider/source binding, 267 canonical Civic part fitments, and the persistent oil-change repair. The approved reference dataset now contains three Civic workflows and proves canonical materialization of the water-pump/downstream pair on a fresh database. Broad repair-knowledge population remains.**

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
- [x] downstream-requirement materialization with evidence-backed source action, target repair, support state, and physical-replacement milestone
- [x] vehicle-identity claim materialization into an existing exact `VehicleConfiguration` publication envelope without rewriting identity fields
- [x] part-fitment claim materialization using the existing `part_fitments` table with insert-only/fail-closed conflict behavior
- [x] safety-campaign claims remain claim-only and fail closed when canonical materialization is attempted
- [x] canonical publication versioning/supersession
- [x] canonical record evidence/audit trail
- [x] dedicated least-privilege materializer boundary
- [x] permanent canonical-publication CI gate
- [x] prevent candidate-only source authority from winning curator conflict resolution
- [x] publish reviewed Honda repair knowledge through reviewer → curator → materializer authority

Remaining Phase 6 work:
- [x] define and persist an explicit trusted `provider_connection` → `catalog_source` binding
- [x] define the trusted execution role/path that resolves provider configuration and its bound source without widening collector authority
- [ ] complete real-provider live ingestion proof through the deployed operator path
- [x] expose safe provider/source configuration and enable/disable controls through authenticated operator/admin flow where required
- [x] broaden canonical materialization to additional domains where the MVP provider pipeline requires it
- [ ] populate **broad** canonical repair knowledge; the approved Civic reference set is still only a small beginning, not broad automotive coverage

Current safety boundary:
- collector/extractor output is candidate data only
- source registration, provider enablement, and binding enablement do **not** start collection by themselves
- external providers have no direct verified/canonical publication authority
- extraction confidence is not source authority
- manually approved source use does not imply automated acquisition permission
- vehicle identity publication does not rewrite stored identity fields
- canonical part fitment is insert-only through the materializer and conflicting existing rows fail closed
- safety campaigns remain verified claim context with no canonical destination in the current architecture
- missing remains missing
- conflicts remain explicit
- AI cannot directly publish canonical automotive truth
- production provider/collector activation is **not** implied by preview configuration

---

## Phase 7 — Primary end-to-end vehicle

Status: **In progress. The 2009 Civic Hybrid now has permanent fresh-database proof for both a standalone repair and a repair that triggers required follow-on work. The water-pump → physical coolant refill/air-bleed chain is project-owner approved, canonically materialized in the runtime gate, and mechanically completion-safe. Systems/assemblies, first-class specifications, observations/photos, and additional representative repair coverage remain.**

Use the 2009 Honda Civic Hybrid as the deepest first validation configuration.

- [x] identity coverage — exact verified `VehicleConfiguration`
- [ ] systems/assemblies coverage
- [x] parts and hardware coverage — 267 reviewed canonical fitments across cooling, HVAC, intake, brakes, and suspension; repair-specific drain washer, water pump, and water-pump seal are represented in approved repair requirements
- [x] tools coverage — oil-change repair includes oil-filter wrench and flat-tip screwdriver; reusable workspace/equipment requirements are also exercised in the water-pump path
- [x] fluids/materials coverage — oil-change includes 0W-20 engine oil with verified quantity/unit; coolant follow-on requires Honda Long Life Antifreeze/Coolant Type 2
- [ ] specifications coverage — torque/capacity remain evidence-backed inside existing repair knowledge where present, but first-class specification-table coverage is still pending
- [x] repair requirements coverage — approved reference repairs load verified requirements through the canonical requirement manifest
- [x] procedures coverage — `engine-oil-filter-change` has 6 ordered actions; `engine-water-pump-replacement` has 4 ordered actions; `cooling-system-refill-air-bleed` has 4 ordered actions
- [x] readiness coverage — fresh-database runtime proofs enforce required missing items before supported work can proceed
- [x] blockers coverage — action-level requirements block progression until verified readiness clears them
- [x] downstream operations coverage — completing `install-water-pump` activates `cooling.refill-air-bleed-after-water-pump`; the source repair remains incomplete until the linked `cooling-system-refill-air-bleed` repair is fully complete and then resolved as `linked_session_complete`
- [ ] observations/photos coverage
- [x] pause/resume coverage — oil-change session pauses after oil drain, preserves the last mechanical checkpoint, and resumes with `Replace the oil filter` as the next verified action
- [x] capability-boundary coverage — approved reference repairs are `diy_supported`; computer/service-tool content is not smuggled into the physical coolant refill/bleed workflow
- [x] completion coverage — standalone and downstream-linked runtime paths both prove mechanically honest completion

Current standalone primary-vehicle repair proof:
- repair key: `engine-oil-filter-change`
- repair definition version: `1`
- requirements: `8`
- procedure actions: `6`
- verified evidence/claim links: `14`
- capability: `diy_supported`
- runtime acceptance: `api/tests/test_reference_repair_runtime.py`
- source: Honda OEM service evidence, project-owner reviewed

Current downstream-operation proof:
- source repair: `engine-water-pump-replacement`
- source requirements: `4`
- source actions: `4`
- physical-replacement trigger action: `install-water-pump`
- downstream requirement: `cooling.refill-air-bleed-after-water-pump`
- downstream support state: `supported`
- target repair: `cooling-system-refill-air-bleed`
- target requirements: `1`
- target actions: `4`
- source classification: `licensed_oem_derived`
- source review: project-owner approved on `2026-09-15`; manual evidence use only; automation disabled
- runtime acceptance: `api/tests/test_reference_downstream_runtime.py`
- permanent CI gate: `.github/workflows/reference-runtime.yml`
- runtime CI proof: `Reference Repair Runtime CI #23` on `1cbd46da63285683ef919b0dd917eff6ffad7142`
- runtime proof: parent becomes `downstream_required_pending` after physical pump installation, premature downstream resolution fails, linked refill/bleed must reach `fully_mechanically_complete`, and only then can the parent resolve to `fully_mechanically_complete`
- repository reference dataset: `api/data/reference/2009_honda_civic_hybrid_repairs_v1/`
- persistent consolidation preview note: only the oil-change repair is currently stored there; the water-pump pair is proved through canonical fresh-database materialization and is not silently auto-seeded

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

PartGraph is still being built on the separate `partgraph-mvp-consolidation` branch. PR #84 is still a draft. The production application has **not** been switched to this consolidation work, and the production database is still deliberately at its older `0020_catalog_coverage` version.

The newest fully tested implementation/data commit is `1cbd46da63285683ef919b0dd917eff6ffad7142`. On that exact commit, the API tests, web tests, data-extraction tests, canonical-publication tests, and reference-repair runtime tests all passed. The Vercel preview also finished successfully on the same commit. The preview database itself is now at schema version `0058_downstream_materializer`.

For the 2009 Honda Civic Hybrid, the preview still has 267 reviewed part-fitment records and the oil-change repair stored as its long-lived verified repair. The repository's approved reference data now has two more repair workflows: water-pump replacement and the coolant refill/air-bleed work that must follow it. These new repairs are not being automatically inserted into the preview database just because a deployment happens. Instead, the permanent test builds them from reviewed evidence through the same restricted publication path PartGraph is designed to use.

The important new behavior is now proven. When the user finishes installing the replacement water pump, PartGraph does **not** say the whole job is done. It automatically creates the required coolant refill/air-bleed work. The water-pump repair stays incomplete while that follow-on job is pending. Starting the follow-on repair is still not enough. PartGraph refuses to clear the requirement until the coolant refill/bleed repair itself is fully completed. Only then can the original water-pump repair become fully mechanically complete.

You approved the Charm.li service-manual mirror for this exact MVP reference work on September 15, 2026. That approval is recorded as human-reviewed, manual evidence use. Automated collection from that source is still turned off. This keeps the source-authority rule intact.

### Phase 0 — Put the repository onto one controlled path

Almost everything here is finished. We identified useful code and data, retired obsolete active paths, moved vehicle facts out of hard-coded application logic, and kept current implementation work on the consolidation branch.

The remaining item is the final merge to `main`. That is intentionally blocked until the production database and deployment cutover can be done in the safe order already defined by the roadmap.

### Phase 1 — Fix behavior that could mislead the user

The main behavior problems are fixed. PartGraph cannot simply mark unsupported computer/service-tool work as complete. It understands that one repair can create another required operation. Repair history, resume behavior, Garage identity, and readiness/inventory handling have been corrected.

Two items remain: hosted proof that private repair photos remain durably stored, and the final full regression campaign that belongs to Phase 9.

### Phase 2 — Make the app survive network and timeout problems safely

The current MVP resilience policy is complete. Offline repair use is read-only: a user can continue viewing already downloaded repair information without a connection, but changes still require the server so there is only one final source of truth.

Offline writing and later synchronization are not part of this MVP. If we add them later, they need their own journal, conflict, and reconciliation rules.

### Phase 3 — Keep private data and powerful actions separated

This phase is functionally complete. Ordinary users, contributors, reviewers, curators, collectors, materializers, and operators have separate jobs and permissions.

A collector may bring information into the waiting area but cannot turn it directly into trusted repair knowledge. A normal user cannot publish automotive truth. Each owner's Garage and repair sessions remain private.

### Phase 4 — Give PartGraph a proper place for every kind of repair information

This is complete for the MVP database structure. PartGraph has storage for all 18 planned areas: exact vehicle identity, systems and assemblies, parts, fitment, interchangeable/superseded parts, physical relationships, fasteners, tools, fluids, specifications, repair definitions, ordered steps, required follow-on work, diagnostics, electrical items, safety limits, evidence/conflicts, and owner repair state.

This means the structure exists. It does **not** mean every car and every repair has already been filled with data.

### Phase 5 — Make database upgrades safe

This phase is complete. We proved a clean future baseline, tested fresh database creation, tested upgrades from the existing production-era database, preserved owner data, repaired the historical migration problem, and proved the adopted baseline can reach the current schema.

Production is still deliberately left at `0020_catalog_coverage`. A working preview does not by itself authorize a production migration.

### Phase 6 — Bring automotive information in without automatically trusting it

Most of the pipeline is built. PartGraph can register sources and providers, save the original raw information, extract possible facts, apply source-authority rules, detect conflicts, require human review, create verified evidence and mechanical claims, and publish approved knowledge through a restricted materializer role.

The NHTSA recall collector is implemented. It keeps recall information in the candidate/review path and does not pretend a general year/make/model recall automatically applies to an exact trim or VIN. A configured NHTSA provider/source connection exists only in the isolated preview.

The new water-pump work also proves that reviewed repair knowledge can publish a required follow-on relationship, not just ordinary steps. The water-pump installation points to the separate coolant refill/bleed repair, and the runtime test reconstructs that relationship from verified evidence instead of hard-coding it in application logic.

What remains in this phase is a real deployed HTTP invocation of the operator-triggered NHTSA ingestion path and much broader repair knowledge. Three approved Civic reference workflows are still only a small test set, not broad automotive coverage.

### Phase 7 — Make the 2009 Honda Civic Hybrid work deeply from beginning to end

This is still the active deep-vehicle phase, but the downstream-repair gap is now closed.

Already proven:
- PartGraph knows the exact 2009 Civic Hybrid configuration used for this test.
- The preview has 267 reviewed part fitments.
- The oil-change repair knows its parts, tools, fluid, readiness requirements, blockers, six ordered actions, pause/resume point, and final dashboard oil-life reset.
- The water-pump reference repair knows the replacement pump, new seal, access/drain requirements, and four ordered actions.
- Installing the water pump creates a separate required coolant refill/air-bleed repair.
- That coolant repair requires the approved coolant and has four ordered physical steps.
- PartGraph refuses to call the water-pump repair fully complete while the coolant refill/bleed work is still unfinished.
- PartGraph also refuses to let an unfinished linked repair satisfy the requirement early.
- After the linked coolant repair is fully complete, the original water-pump repair can finally become fully mechanically complete.
- Computer/service-tool instructions are kept out of this physical DIY coolant follow-on workflow.

Still missing before Phase 7 is complete:
- actual primary-vehicle systems/assemblies data coverage
- first-class specification records rather than relying only on values embedded in existing repair evidence
- observations/photo coverage
- additional representative Civic repairs so the deep vehicle proof is not based only on oil change and the water-pump/coolant chain

The next unchecked Phase 7 item in the existing path is **systems/assemblies coverage**. After that, the remaining Phase 7 gaps stay in their existing roadmap order; this update does not move us to Phase 8 early.

### Phase 8 — Prove the same design works on five different vehicle models

This has not started because Phase 7 is not finished.

After the deep Civic work is complete, the remaining reference vehicles are the 2015 Toyota Camry, 2018 Ford F-150, 2020 Subaru Forester, and 2022 Hyundai Tucson. They must be added through data, not by adding make/model/year/trim branches to application code.

### Phase 9 — Run the final MVP test campaign

The final campaign has not started as a single finished-MVP exercise, although many permanent tests already run on every relevant change.

The final campaign will cover unit/domain behavior, APIs, authentication/security, owner isolation, migrations, production-copy migration safety, full-stack behavior, verified guidance, browser flows, randomized cases, all five reference vehicles, offline/degraded behavior, timeout recovery, downstream repairs, unsupported-computer boundaries, durable photos, source-code data checks, and role permissions.

The water-pump runtime test is now permanent evidence for the downstream-repair behavior, but the final Phase 9 downstream test item remains unchecked until the complete MVP suite is run as a whole.

### Phase 10 — Move the finished MVP into production

This has not started and still requires explicit production approval.

When that point is reached, we will merge only an exact green commit, deploy frontend and backend from the same source version, apply only already-tested database changes, verify health and real owner state, and run production-safe smoke checks. Unreviewed data will not be inserted as trusted repair truth to make a launch appear complete.

### Safety rules that remain in force

Updating this progress file does **not** authorize merging PR #84, migrating the production database, enabling collectors/providers in production, deleting Git or Neon branches, weakening source-authority rules, or skipping human evidence review.

If information is missing, PartGraph must keep it missing instead of guessing. If sources disagree, the conflict remains visible until it is resolved. Candidate or AI-produced information cannot publish itself as canonical automotive truth.

The Charm.li approval is narrow: it covers the manually reviewed 2009 Civic Hybrid water-pump and physical coolant refill/air-bleed MVP evidence approved on September 15, 2026. It does not enable automated collection from Charm.li or grant blanket approval to unrelated material.

### Exact place to resume work

The water-pump downstream proof is complete. The current path should resume at the next unchecked primary-vehicle item in Phase 7: **systems/assemblies coverage for the 2009 Honda Civic Hybrid**.

That work must remain data-driven and use the existing canonical/evidence architecture. It must not add vehicle-specific Python, TypeScript, SQL application branches, relax source authority, or change the roadmap order. The separate Phase 6 live NHTSA HTTP-ingestion proof also remains explicitly pending and has not been reclassified as complete by this Phase 7 progress.
