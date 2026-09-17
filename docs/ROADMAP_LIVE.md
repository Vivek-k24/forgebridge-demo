# PartGraph MVP Roadmap — Live Progress Copy

Status: **Live progress tracker**  
Architecture authority: `docs/BLUEPRINT.md`  
Implementation-sequence source: `docs/ROADMAP.md`  
Maintenance rule: **update this file directly on `main` as soon as a roadmap task is completed. Do not wait for the implementation branch to merge or for its PR to close. Keep the technical tracker and the `Layman Live progress` section synchronized so they describe the same completed, pending, and next work without changing roadmap scope, order, or architecture.**

Last updated: **2026-09-16**

Current exact implementation proof tracked here:
- active implementation branch: `partgraph-mvp-consolidation`
- latest exact green implementation/data commit: `e16136275a70671b36c384d843a82bfb2012bef7`
- MVP Final Validation CI: passed (`#2`)
- full API CI: passed (`#987`)
- Web CI: passed (`#850`)
- extraction/provider-ingestion pipeline CI: passed (`#318`)
- canonical publication CI: passed (`#258`)
- reference repair runtime CI: passed (`#257`)
- database reliability CI: passed (`#110`)
- operational observability CI: passed (`#72`)
- Web dependency advisory CI: passed (`#114`)
- latest observed READY Vercel consolidation preview for the Phase 8 Tucson data line: `dpl_2f9YRc4BEN9nHc3PJRHdU9fwPBy3` on `6862983d386a879fd7ef4ac5acd0c2e7bb27a6e5`; the exact green `e1613627...` proof is the GitHub CI/runtime proof after the Phase 9 validation workflow addition
- consolidation preview database schema: `0059_primary_vehicle_domains`
- production database: intentionally unchanged at `0020_catalog_coverage`
- PR #84: remains draft/unmerged

Phase 7 is complete for the primary deep-test vehicle, the 2009 Honda Civic Hybrid. Fresh-database runtime proof covers exact identity, reviewed fitments, requirements, tools, fluids, ordered procedures, readiness and blockers, pause/resume, honest completion, a repair-triggered downstream repair, first-class systems/assemblies, first-class specifications, and owner-scoped observations/photos. The representative repair set contains a standalone oil-change workflow plus the water-pump replacement and its separately required coolant refill/air-bleed workflow. No make/model/year/trim application-code branch was added to achieve that coverage.

Phase 8 is also complete. The same generic identity/publication/readiness/guidance/completion code now executes reviewed reference repairs for the 2015 Toyota Camry, 2018 Ford F-150, 2020 Subaru Forester, and 2022 Hyundai Tucson in addition to the Phase 7 Civic proof. The four additional datasets are selected through `api/data/reference/phase8_reference_fleet_v1.json` and exercised by one data-indexed runtime test; no make/model/year/trim application service or conditional branch was added for the new vehicles.

Phase 9 is now in progress. The first fresh final-validation layer is complete: `.github/workflows/mvp-final-validation.yml` runs the release-oriented unit/domain contract set together rather than relying only on scattered historical greens. On `e16136275a70671b36c384d843a82bfb2012bef7`, that gate and every established exact-head regression passed. API-level final-MVP validation is the next Phase 9 task.

The new primary-vehicle canonical domains are data-driven. Reviewed exact-vehicle claims materialize an `Engine` system, `Engine cooling system` subsystem, and `Engine water-pump assembly`; first-class specifications record the 3.4 US qt engine-oil change capacity with filter and 39 N·m oil-drain-bolt torque. The same source-authority, verified-evidence, MechanicalClaim, restricted-materializer, conflict-quarantine, canonical-version, and evidence-link rules used by existing canonical knowledge apply to these domains.

The long-lived consolidation preview remains deliberately non-seeding. It is migrated to `0059_primary_vehicle_domains`, but deployment did not silently create Civic structure/specification rows or Phase 8 reference repairs; reviewed facts are reconstructed and proven through canonical materialization on fresh databases. The preview still contains previously published knowledge unless knowledge is explicitly published through the authorized path.

Owner observation/photo coverage is proven at repair-session runtime: create an owner observation, attach photo evidence, list it, retrieve and hash-verify the stored content, delete it, and verify removal. This closes the Phase 7 observation/photo behavior requirement. It does **not** close the separate Phase 1/Phase 9 hosted durable-photo-storage requirement; hosted persistence remains pending exactly where the roadmap already places it.

Charm.li service-manual mirror evidence for the approved water-pump/coolant MVP reference path remains classified `licensed_oem_derived`, project-owner reviewed on 2026-09-15, and approved for manual evidence use only. `automation_allowed` remains `false`.

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

Status: **In progress. The generic evidence/provider/publication pipeline is implemented and green. The preview has an enabled NHTSA provider/source binding, 267 canonical Civic part fitments, and the persistent oil-change repair. The approved Civic reference set now also proves repair/downstream, structure, and specification canonical materialization on fresh databases. Broad repair-knowledge population remains.**

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
- [x] vehicle-structure claim materialization into systems/subsystems/assemblies with parent integrity, insert-only publication, evidence/version envelopes, and explicit conflict quarantine
- [x] vehicle-specification claim materialization into first-class definitions/values with insert-only publication, evidence/version envelopes, and explicit conflict quarantine
- [x] safety-campaign claims remain claim-only and fail closed when canonical materialization is attempted
- [x] canonical publication versioning/supersession
- [x] canonical record evidence/audit trail
- [x] dedicated least-privilege materializer boundary
- [x] permanent canonical-publication CI gate
- [x] prevent candidate-only source authority from winning curator conflict resolution
- [x] publish reviewed Honda knowledge through reviewer → curator → materializer authority

Remaining Phase 6 work:
- [x] define and persist an explicit trusted `provider_connection` → `catalog_source` binding
- [x] define the trusted execution role/path that resolves provider configuration and its bound source without widening collector authority
- [ ] complete real-provider live ingestion proof through the deployed operator path
- [x] expose safe provider/source configuration and enable/disable controls through authenticated operator/admin flow where required
- [x] broaden canonical materialization to additional domains where the MVP provider pipeline requires it
- [ ] populate **broad** canonical repair knowledge; the reviewed Civic + Phase 8 reference set is still a narrow validation corpus, not broad automotive coverage

Current safety boundary:
- collector/extractor output is candidate data only
- source registration, provider enablement, and binding enablement do **not** start collection by themselves
- external providers have no direct verified/canonical publication authority
- extraction confidence is not source authority
- manually approved source use does not imply automated acquisition permission
- vehicle identity publication does not rewrite stored identity fields
- canonical part fitment is insert-only through the materializer and conflicting existing rows fail closed
- canonical structure/specification publication is insert-only; contradictory reviewed evidence enters explicit conflict state rather than overwriting trusted rows
- safety campaigns remain verified claim context with no canonical destination in the current architecture
- missing remains missing
- conflicts remain explicit
- AI cannot directly publish canonical automotive truth
- production provider/collector activation is **not** implied by preview configuration

---

## Phase 7 — Primary end-to-end vehicle

Status: **Complete.** The 2009 Honda Civic Hybrid satisfies the Phase 7 deep-vehicle exit gate with multiple representative repairs and all listed primary-vehicle coverage exercised through data/evidence and generic runtime behavior rather than vehicle-specific application code.

Use the 2009 Honda Civic Hybrid as the deepest first validation configuration.

- [x] identity coverage — exact verified `VehicleConfiguration`
- [x] systems/assemblies coverage — reviewed exact-vehicle claims canonically materialize `Engine` → `Engine cooling system` → `Engine water-pump assembly`
- [x] parts and hardware coverage — 267 reviewed canonical fitments across cooling, HVAC, intake, brakes, and suspension; repair-specific drain washer, water pump, and water-pump seal are represented in approved repair requirements
- [x] tools coverage — oil-change repair includes oil-filter wrench and flat-tip screwdriver; reusable workspace/equipment requirements are also exercised in the water-pump path
- [x] fluids/materials coverage — oil-change includes 0W-20 engine oil with verified quantity/unit; coolant follow-on requires Honda Long Life Antifreeze/Coolant Type 2
- [x] specifications coverage — first-class canonical values include 3.4 US qt engine-oil change capacity with filter and 39 N·m engine-oil drain-bolt torque
- [x] repair requirements coverage — approved reference repairs load verified requirements through the canonical requirement manifest
- [x] procedures coverage — `engine-oil-filter-change` has 6 ordered actions; `engine-water-pump-replacement` has 4 ordered actions; `cooling-system-refill-air-bleed` has 4 ordered actions
- [x] readiness coverage — fresh-database runtime proofs enforce required missing items before supported work can proceed
- [x] blockers coverage — action-level requirements block progression until verified readiness clears them
- [x] downstream operations coverage — completing `install-water-pump` activates `cooling.refill-air-bleed-after-water-pump`; the source repair remains incomplete until the linked `cooling-system-refill-air-bleed` repair is fully complete and then resolved as `linked_session_complete`
- [x] observations/photos coverage — owner-scoped repair runtime proves observation creation plus attached photo create/list/read/hash/delete behavior; hosted durable persistence remains separately pending under Phase 1/9
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
- runtime proof: parent becomes `downstream_required_pending` after physical pump installation, premature downstream resolution fails, linked refill/bleed must reach `fully_mechanically_complete`, and only then can the parent resolve to `fully_mechanically_complete`

Current primary-vehicle domain/memory proof:
- approved data fixture: `api/data/reference/2009_honda_civic_hybrid_profile_v1/canonical_coverage.json`
- generic canonical materializer: `api/partgraph/knowledge/vehicle_domain_materialization.py`
- authority/schema migration: `api/migrations/versions/0059_primary_vehicle_domains.py`
- generic materialization test: `api/tests/test_vehicle_domain_materialization_database.py`
- least-privilege materializer test: `api/tests/test_vehicle_domain_materializer_database_privileges.py`
- exact Civic structure/specification + owner observation/photo runtime: `api/tests/test_reference_primary_vehicle_runtime.py`
- permanent reference gate: `.github/workflows/reference-runtime.yml`
- exact runtime CI proof: `Reference Repair Runtime CI #43` on `7b1d7df912bdc5749cad46efee771f97c5a20107`
- canonical publication CI proof: `Canonical Publication CI #65` on the same commit
- full API regression proof: `API CI/CD #809` on the same commit
- preview schema: `0059_primary_vehicle_domains`
- persistent-preview boundary: deployment created no Civic structure/specification rows automatically; reviewed facts are materialized only through the authorized publication path

Exit gate: **satisfied.** Representative repairs work start-to-finish without vehicle-specific code changes.

---

## Phase 8 — Five-model reference fleet

Status: **Complete.** The five-model validation fleet now executes through the same generic source-review, identity materialization, repair-definition publication, readiness, guidance, and completion code paths.

- [x] Populate the remaining reference fleet through data only.

Phase 8 data/runtime proof:
- 2009 Honda Civic Hybrid — Phase 7 deep proof remains the primary vehicle and supplies the first model-family runtime coverage
- 2015 Toyota Camry — reviewed Toyota owner-manual evidence; `license-plate-light-bulb-replacement`
- 2018 Ford F-150 — reviewed Ford owner-manual evidence; `license-plate-light-bulb-replacement`
- 2020 Subaru Forester — reviewed Subaru owner-manual evidence; `backup-light-bulb-replacement`
- 2022 Hyundai Tucson, Smartstream G 2.5 GDI — reviewed Hyundai owner-manual evidence; `cabin-air-filter-replacement`
- fleet index: `api/data/reference/phase8_reference_fleet_v1.json`
- generic fleet runtime: `api/tests/test_reference_fleet_runtime.py`
- permanent gate: `.github/workflows/reference-runtime.yml`
- exact five-model proof head: `5048467d80dc9df782a2ba300f31fee565d8db30`
- exact fleet runtime proof: `Reference Repair Runtime CI #256`

The Phase 8 runner is data-indexed. Camry, F-150, Forester, and Tucson are discovered from the fleet index and execute the same runtime implementation. No make/model/year/trim conditional was added to the application or the test runner for any of them.

Rule: adding another vehicle may require more data, but must not require make/model/year/trim application-code branches.

Exit gate: **satisfied.** The same source code executes the selected reference-fleet workflows without a make-specific application service.

---

## Phase 9 — Build the fresh MVP validation suite

Status: **In progress. The fresh release-oriented validation campaign has started; the unit/domain layer is complete and API-level final-MVP validation is next. Existing permanent CI gates remain active.**

- [x] unit/domain tests for final MVP behavior
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

Completed Phase 9 proof so far:
- final-validation workflow: `.github/workflows/mvp-final-validation.yml`
- unit/domain contract job: `Phase 9 unit/domain contracts`
- exact proof head: `e16136275a70671b36c384d843a82bfb2012bef7`
- proof run: `MVP Final Validation CI #2`
- contract set covers fail-closed source authority and repair materialization, unsupported computer/service-tool boundaries, provider network safety, provider/API/browser timeout hierarchy, ambiguous-write recovery, and vehicle-fact externalization
- all eight established exact-head regression workflows also passed on the same commit

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

**Phase 9 is now in progress.** The five-model Phase 8 proof remains complete, and the first fresh final-MVP validation layer has now been run successfully.

The exact green implementation/data commit is `e16136275a70671b36c384d843a82bfb2012bef7`. On that commit, the new MVP Final Validation unit/domain job passed, along with the full API suite, web suite, extraction/staging suite, canonical-publication suite, reference runtime suite, database-reliability suite, observability suite, and web dependency advisory suite. The latest observed READY Vercel preview on the preceding Phase 8 application/data line remains `dpl_2f9YRc4BEN9nHc3PJRHdU9fwPBy3`, and the preview database schema remains `0059_primary_vehicle_domains`.

The production application has **not** been switched to the consolidation branch. PR #84 remains a draft and unmerged, and the production database remains deliberately at `0020_catalog_coverage`.

The Civic Hybrid remains the deep test vehicle. PartGraph has proof for much more than a list of parts on that car: vehicle structure, specifications, multiple repairs, downstream work, readiness, blockers, pause/resume, observations/photos, and honest completion. The additional Phase 8 vehicles are intentionally narrower validation cases whose job is to prove that the generic system really carries to other manufacturers and years.

For the four added vehicles, the application reads reviewed data and uses the same runtime machinery: a Toyota Camry license-plate bulb repair, a Ford F-150 license-plate bulb repair, a Subaru Forester backup-light bulb repair, and a gasoline 2022 Hyundai Tucson cabin-air-filter repair. One fleet index selects those datasets, and one generic fleet test runs them. We did not add `if Toyota`, `if Ford`, `if Subaru`, or `if Hyundai` behavior.

The trusted-data rules are unchanged. An approved exact-vehicle source supports a reviewed claim; a restricted materializer publishes it; contradictory claims become explicit conflicts; ordinary users and data collectors cannot directly rewrite trusted automotive knowledge. Deployment itself does not insert the reference facts automatically.

PartGraph also proves owner observations and photos inside a repair session. A user observation can be created, a photo can be attached to it, both can be listed again, the stored photo can be read and hash-checked, and the photo can be deleted cleanly. This proves the Phase 7 repair-memory behavior. It does **not** mean hosted durable photo storage is finished; proving that photos survive the real hosted environment remains a separate Phase 1/Phase 9 item.

### Phase 0 — Put the repository onto one controlled path

Almost everything in this phase is finished. We identified useful code and data, retired obsolete active paths, removed vehicle facts from application-code branching, and kept implementation on the consolidation branch.

The remaining item is the final merge to `main`, which stays blocked until the production database/deployment cutover can happen in the safe order already defined.

### Phase 1 — Fix behavior that could mislead the user

The main behavioral problems are fixed. Unsupported computer/service-tool work cannot be falsely marked complete, required follow-on work is understood, repair state resumes correctly, and Garage/readiness/inventory behavior is reconciled.

Hosted durable private-photo persistence is still pending. The final complete regression campaign is also intentionally reserved for Phase 9.

### Phase 2 — Survive network and timeout problems safely

The MVP policy here is complete. Offline repair use is read-only: already downloaded information can still be viewed, while writes remain server-authoritative.

Offline writing and reconciliation are not part of this MVP.

### Phase 3 — Keep private data and powerful actions separated

Functionally complete. Users, contributors, reviewers, curators, collectors, materializers, and operators have separate permissions. Owner Garage/session information remains private, while canonical automotive knowledge is shared but read-only to ordinary users.

### Phase 4 — Give the database a place for the full repair model

Complete for the MVP structure. The database can represent all 18 planned areas, including vehicle structure, parts, fitment, fasteners, tools, fluids, specifications, repairs, dependencies, downstream work, diagnostics, electrical data, safety limits, evidence/conflicts, and owner repair state.

The structure being complete does not mean broad data for every vehicle is already populated.

### Phase 5 — Make database upgrades safe

Complete. Fresh database creation, production-era upgrades, owner-data preservation, the adopted baseline, historical migration repair, and schema equivalence are tested.

Production remains intentionally at `0020_catalog_coverage` until a separate production decision.

### Phase 6 — Bring automotive information in without automatically trusting it

Most of the pipeline is built. PartGraph can register sources/providers, preserve raw data, stage candidate facts, apply source-authority rules, detect conflicts, require human review, create verified evidence and claims, and publish through restricted materializer roles.

The Phase 7/8 work reuses this mechanism for vehicle structure, specifications, additional identities, requirements, and procedures. These are not vehicle-specific shortcuts; the same generic path is what allowed the reference fleet to expand.

Still pending in Phase 6 are the real deployed HTTP proof of operator-triggered NHTSA ingestion and broad automotive repair knowledge beyond the narrow reviewed validation set.

### Phase 7 — Make the 2009 Honda Civic Hybrid work deeply from beginning to end

**Complete.**

The completed proof includes exact Civic Hybrid identity, 267 reviewed part fitments, an engine → cooling system → water-pump assembly hierarchy, first-class oil-capacity and drain-bolt-torque specifications, oil-change parts/tools/fluid/readiness/blockers and six ordered actions, pause/resume, water-pump replacement, the required coolant refill/air-bleed follow-on repair, owner observations/photos, capability boundaries, and mechanically honest completion.

Most importantly, the application did not need a special `if 2009 Honda Civic Hybrid` code path. The vehicle facts live in data/evidence; the application uses the same generic publication and repair-runtime machinery.

That satisfies the Phase 7 exit gate.

### Phase 8 — Prove the same design works on five different vehicle models

**Complete.**

The full validation fleet is now represented:
- 2009 Honda Civic Hybrid — deep primary proof
- 2015 Toyota Camry — license-plate light bulb replacement
- 2018 Ford F-150 — license-plate light bulb replacement
- 2020 Subaru Forester — backup-light bulb replacement
- 2022 Hyundai Tucson with Smartstream G 2.5 GDI — cabin-air-filter replacement

Camry, F-150, Forester, and Tucson are listed in one data index and run by one generic reference-fleet test. The test creates an unverified configuration from the data, publishes reviewed vehicle identity through the restricted materializer, publishes reviewed repair requirements/actions, proves readiness blockers, executes the ordered physical repair actions, and requires final mechanical completion. The same source code does this for every listed dataset.

No Toyota-, Ford-, Subaru-, or Hyundai-specific application service or make/model conditional was introduced. That satisfies the Phase 8 exit gate.

### Phase 9 — Run the final MVP test campaign

**In progress.** The first layer is complete: PartGraph now has a dedicated final-validation workflow that reruns the core unit/domain contracts together as one release-oriented checkpoint instead of depending only on tests that happened to be green in separate historical workflows.

That first Phase 9 job checks the most important low-level contracts currently available without requiring a database integration environment: source authority fails closed, repair materialization cannot bypass its evidence rules, unsupported computer/service-tool work stays outside supported mechanical completion, provider URLs and redirects cannot target private/internal networks, provider/API/browser timeout budgets stay ordered, ambiguous committed writes require authoritative recovery, and vehicle facts remain externalized from application code.

The new job passed on `e16136275a70671b36c384d843a82bfb2012bef7`, and every established regression workflow also passed on that same commit. The **next Phase 9 task is API tests for final MVP behavior**. Security, owner isolation, migrations, browser flows, randomized/reference-fleet acceptance, offline/degraded behavior, timeout recovery, downstream semantics, durable hosted photos, data-free-source-code checks, and RBAC remain later Phase 9 items.

### Phase 10 — Move the finished MVP into production

Not started and still requires explicit production approval. The eventual cutover must use one exact green commit, synchronized frontend/backend code, validated schema changes, health checks, real owner-state checks, and production-safe smoke tests. Unreviewed automotive data will not be seeded as canonical truth.

### Safety rules that remain in force

Updating this tracker does **not** authorize merging PR #84, migrating production, enabling production collectors/providers, deleting Git or Neon branches, weakening source authority, or skipping human evidence review.

If information is missing, PartGraph keeps it missing instead of guessing. If trusted sources disagree, the conflict remains explicit until reviewed. AI or candidate data cannot publish itself as canonical automotive truth.

Charm.li approval remains narrow: manually reviewed evidence for the approved 2009 Civic Hybrid water-pump and physical coolant refill/air-bleed MVP path only. Automated Charm.li collection remains disabled.

### Exact place to resume work

Phase 9 is in progress. The next roadmap task is **API tests for final MVP behavior** in the fresh MVP validation suite.

The separate Phase 6 live NHTSA HTTP-ingestion proof and broad repair-knowledge work, Phase 1 hosted durable-photo proof, remaining Phase 9 validation campaign, and production cutover requirements all remain pending in their existing roadmap locations.