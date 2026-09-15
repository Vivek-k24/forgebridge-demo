# PartGraph MVP Roadmap — Live Progress Copy

Status: **Live progress tracker**  
Architecture authority: `docs/BLUEPRINT.md`  
Implementation-sequence source: `docs/ROADMAP.md`  
Maintenance rule: **update this file directly on `main` as soon as a roadmap task is completed. Do not wait for the implementation branch to merge or for its PR to close.**

Last updated: **2026-09-14**

Current exact implementation proof tracked here:
- active implementation branch: `partgraph-mvp-consolidation`
- latest exact green implementation commit: `384cd95edadaf36bde621b6b4deb95c2a3ca3092`
- full API CI: passed (`#776`)
- Web CI: passed (`#639`)
- extraction/provider-ingestion pipeline CI: passed (`#53`)
- canonical publication CI: passed
- Vercel consolidation preview: READY on the same commit
- consolidation preview database: `0057_nhtsa_ingest_audit`
- production database: intentionally unchanged at `0020_catalog_coverage`
- PR #84: remains draft/unmerged

The consolidation preview now contains 267 reviewed canonical Civic Hybrid part fitments and the first fully canonical repair workflow: `engine-oil-filter-change` version 1, with 8 requirements, 6 ordered procedure actions, `diy_supported` capability, and 14 verified evidence links. The final non-skippable action resets the Maintenance Minder engine-oil-life display to 100% using the vehicle's dashboard controls.

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

Status: **In progress. The exact 2009 Civic Hybrid identity, reviewed parts/fitment coverage, first tool/fluid/requirement set, first verified procedure, and DIY capability classification are now canonical. Runtime session/readiness/completion validation and additional repair domains remain.**

Use the 2009 Honda Civic Hybrid as the deepest first validation configuration.

- [x] identity coverage — exact verified `VehicleConfiguration`
- [ ] systems/assemblies coverage
- [x] parts and hardware coverage — 267 reviewed canonical fitments across cooling, HVAC, intake, brakes, and suspension; repair-specific drain washer also modeled as a requirement
- [x] tools coverage — first canonical repair includes oil-filter wrench and flat-tip screwdriver
- [x] fluids/materials coverage — first canonical repair includes 0W-20 engine oil with verified quantity/unit
- [ ] specifications coverage — torque/capacity are evidence-backed inside the repair workflow, but first-class specification-table coverage is still pending
- [x] repair requirements coverage — first canonical repair has 8 verified requirement uses
- [x] procedures coverage — `engine-oil-filter-change` v1 has 6 ordered, non-skippable actions with evidence; final action resets engine oil life to 100%
- [ ] readiness coverage
- [ ] blockers coverage
- [ ] downstream operations coverage
- [ ] observations/photos coverage
- [ ] pause/resume coverage
- [x] capability-boundary coverage — first canonical repair is explicitly `diy_supported`; dashboard reset uses physical vehicle controls rather than scan-tool/computer authority
- [ ] completion coverage

Current primary-vehicle canonical repair proof:
- repair key: `engine-oil-filter-change`
- repair definition version: `1`
- requirements: `8`
- procedure actions: `6`
- verified evidence/claim links: `14`
- capability: `diy_supported`
- source: Honda OEM service evidence, project-owner reviewed
- repository reference dataset: `api/data/reference/2009_honda_civic_hybrid_repairs_v1/`

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

Existing permanent CI, including migration history, adopted-baseline equivalence, RBAC, source-authority, extraction, canonical publication, container build, and readiness smoke, remains active and is not discarded while Phase 9 is pending.

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
