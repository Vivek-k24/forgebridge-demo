# PartGraph MVP Roadmap — Live Progress Copy

Status: **Live progress tracker**  
Architecture authority: `docs/BLUEPRINT.md`  
Implementation-sequence source: `docs/ROADMAP.md`  
Maintenance rule: **update this file directly on `main` as soon as a roadmap task is completed. Do not wait for the implementation branch to merge or for its PR to close. Keep the technical tracker and the `Layman Live progress` section synchronized so they describe the same completed, pending, and next work without changing roadmap scope, order, or architecture.**

Last updated: **2026-09-18**

Current exact implementation proof tracked here:
- active implementation branch: `partgraph-mvp-consolidation`
- latest exact GitHub-green implementation/data commit: `274fdd7d33d5b8d58759f52c9abe1bfe6ca4b988`
- MVP Final Validation CI: passed (`#189`, attempt 2; all 18 GitHub Phase 9 jobs)
- full API CI: passed (`#1080`)
- Web CI: passed (`#943`)
- extraction/provider-ingestion pipeline CI: passed (`#417`)
- canonical publication CI: passed (`#354`)
- reference repair runtime CI: passed (`#365`)
- database reliability CI: passed (`#204`)
- operational observability CI: passed (`#165`)
- Web dependency advisory CI: passed (`#207`)
- exact-head Vercel preview: `dpl_GeUdp2NqutbBBYHiTB6hxLKWdm1U` failed closed at the durable-photo probe because Preview has `VERCEL_OIDC_TOKEN` but no connected Blob store (`BLOB_STORE_ID` absent and no legacy `BLOB_READ_WRITE_TOKEN`); this is the remaining hosted durable-photo blocker, not an RBAC failure
- last fully READY Vercel Phase 9 implementation head before the fail-closed photo probe: `e92967712fef381b37068b87c236d15509677ada`
- consolidation preview database schema: `0059_primary_vehicle_domains`
- production database: intentionally unchanged at `0020_catalog_coverage`
- PR #84: remains draft/unmerged

Phase 7 is complete for the primary deep-test vehicle, the 2009 Honda Civic Hybrid. Fresh-database runtime proof covers exact identity, reviewed fitments, requirements, tools, fluids, ordered procedures, readiness and blockers, pause/resume, honest completion, a repair-triggered downstream repair, first-class systems/assemblies, first-class specifications, and owner-scoped observations/photos. The representative repair set contains a standalone oil-change workflow plus the water-pump replacement and its separately required coolant refill/air-bleed workflow. No make/model/year/trim application-code branch was added to achieve that coverage.

Phase 8 is also complete. The same generic identity/publication/readiness/guidance/completion code now executes reviewed reference repairs for the 2015 Toyota Camry, 2018 Ford F-150, 2020 Subaru Forester, and 2022 Hyundai Tucson in addition to the Phase 7 Civic proof. The four additional datasets are selected through `api/data/reference/phase8_reference_fleet_v1.json` and exercised by one data-indexed runtime test; no make/model/year/trim application service or conditional branch was added for the new vehicles.

Phase 9 is now in progress. Seventeen roadmap validation items are complete: all code-owned Phase 9 checks through RBAC authorization. The final-validation workflow now has eighteen GitHub jobs because it also runs the code-side durable-photo contracts while the separate hosted persistence requirement remains open. On `274fdd7d33d5b8d58759f52c9abe1bfe6ca4b988`, MVP Final Validation CI #189 attempt 2 completed successfully with all eighteen jobs green, and all eight established exact-head regression workflows also passed. The RBAC layer proves the Owner/Contributor/Reviewer/Curator/Operator hierarchy and reruns the database privilege boundaries for app, contributor, reviewer, curator, materializer, operator, provenance, downstream, and capability access. The real Vercel preview still fails only at the photo probe because no Preview Blob store is connected, so durable photo persistence is now the sole remaining Phase 9 checkbox.

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

Status: **In progress. Seventeen roadmap validation items are complete, including RBAC authorization. Every code-owned Phase 9 validation layer is green. The code-side durable-photo job is also green, but the hosted durable-photo item remains blocked because the Vercel Preview project has no connected Blob store. Durable photo persistence is the only remaining Phase 9 checkbox. Existing permanent CI gates remain active.**

- [x] unit/domain tests for final MVP behavior
- [x] API tests for final MVP behavior
- [x] authentication/security tests
- [x] RLS/owner-isolation tests
- [x] migration tests
- [x] production-copy migration validation
- [x] full-stack integration
- [x] verified-guidance integration
- [x] browser E2E
- [x] randomized acceptance
- [x] reference-fleet acceptance
- [x] offline/degraded behavior
- [x] timeout/ambiguous-write recovery
- [x] downstream-operation semantics
- [x] unsupported computer boundary
- [ ] durable photo persistence
- [x] data-free-source-code check
- [x] RBAC authorization tests

Completed Phase 9 proof so far:
- final-validation workflow: `.github/workflows/mvp-validation.yml`
- unit/domain contract job: `Phase 9 unit/domain contracts`
- API contract job: `Phase 9 API contracts`
- API contract suite: `api/tests/test_mvp_api_contracts.py`
- authentication/security job: `Phase 9 authentication/security contracts`
- authentication/security suite: `api/tests/test_mvp_auth_security.py`
- RLS/owner-isolation job: `Phase 9 RLS/owner-isolation contracts`
- RLS/owner-isolation suite: `api/tests/test_mvp_owner_isolation.py`
- migration job: `Phase 9 migration contracts`
- migration suite: `api/tests/test_mvp_migrations.py`
- production-copy migration job: `Phase 9 production-copy migration contracts`
- production-copy verifier: `api/scripts/verify_production_copy_upgrade.py`
- full-stack job: `Phase 9 full-stack integration`
- full-stack verifier: `api/scripts/verify_full_stack_runtime.py`
- verified-guidance job: `Phase 9 verified-guidance integration`
- verified-guidance verifier: `api/scripts/verify_verified_guidance_integration.py`
- browser E2E job: `Phase 9 browser E2E`
- browser E2E verifier: `api/scripts/verify_browser_e2e.py`
- randomized-acceptance job: `Phase 9 randomized acceptance`
- randomized-acceptance suite: `api/tests/test_mvp_randomized_acceptance.py`
- randomized-acceptance fixed seed: `20260917`
- reference-fleet acceptance job: `Phase 9 reference-fleet acceptance`
- reference-fleet acceptance suites: `api/tests/test_reference_*_runtime.py`
- offline/degraded job: `Phase 9 offline/degraded behavior`
- offline/degraded browser verifier: `api/scripts/verify_offline_degraded_e2e.py`
- timeout/recovery job: `Phase 9 timeout/ambiguous-write recovery`
- timeout/recovery server suite: `api/tests/test_mvp_timeout_recovery.py`
- commit-disconnect recovery suite: `api/tests/test_database_write_recovery.py`
- timeout hierarchy suite: `api/tests/test_provider_timeout_hierarchy.py`
- timeout/recovery browser verifier: `api/scripts/verify_timeout_ambiguous_write_e2e.py`
- downstream-operation semantics job: `Phase 9 downstream-operation semantics`
- downstream canonical materialization suite: `api/tests/test_downstream_materialization_database.py`
- downstream materializer privilege suite: `api/tests/test_downstream_materializer_database_privileges.py`
- downstream runtime semantics suite: `api/tests/test_reference_downstream_runtime.py`
- unsupported computer boundary job: `Phase 9 unsupported computer boundary`
- unsupported computer runtime suite: `api/tests/test_mvp_unsupported_computer_boundary.py`
- computer-boundary definition suite: `api/tests/test_repair_materialization_policy.py`
- capability boundary privilege suite: `api/tests/test_capability_database_privileges.py`
- durable-photo code-side job: `Phase 9 durable photo persistence`
- hosted/local storage suite: `api/tests/test_hosted_photo_storage.py`
- durable lifecycle suite: `api/tests/test_reference_photo_storage_runtime.py`
- hosted Preview probe: `api/scripts/verify_hosted_photo_persistence.py`
- data-free source-code job: `Phase 9 data-free source-code check`
- data-free invariant suite: `api/tests/test_data_free_source_code.py`
- generic reference fixture index: `api/data/reference/primary_reference_bundle_v1.json`
- generic test fixture loader: `api/tests/reference_fixture_support.py`
- RBAC authorization job: `Phase 9 RBAC authorization tests`
- human role hierarchy suite: `api/tests/test_mvp_rbac_authorization.py`
- RBAC database suites: `api/tests/test_rbac_database_privileges.py`, `api/tests/test_pipeline_database_privileges.py`, `api/tests/test_materializer_database_privileges.py`, `api/tests/test_part_catalog_materializer_database_privileges.py`, `api/tests/test_vehicle_domain_materializer_database_privileges.py`, `api/tests/test_downstream_materializer_database_privileges.py`, `api/tests/test_source_authority_operator_database_privileges.py`, `api/tests/test_provenance_database_privileges.py`, and `api/tests/test_capability_database_privileges.py`
- operator role-management guardrail suite: `api/tests/test_operator_role_management.py`
- exact GitHub proof head: `274fdd7d33d5b8d58759f52c9abe1bfe6ca4b988`
- proof run: `MVP Final Validation CI #189`, attempt 2
- unit/domain contracts cover fail-closed source authority and repair materialization, unsupported computer/service-tool boundaries, provider network safety, provider/API/browser timeout hierarchy, ambiguous-write recovery, and vehicle-fact externalization
- API contracts run against the FastAPI application with a migrated fresh PostgreSQL service and verify live/readiness health, platform response headers, standardized 404/405 error envelopes, request-size enforcement, authenticated Garage/repair collection wiring, and the core MVP repair HTTP surface
- authentication/security contracts run against the real authentication/session path with a migrated fresh PostgreSQL service and verify unauthenticated rejection, CSRF and exact-origin enforcement, secure HttpOnly session-cookie/HSTS behavior, Argon2 password hashing, hashed session-token storage, logout revocation, non-enumerating invalid-login responses, and persisted failed-login rate limiting through 429
- existing exact-origin/CSP contracts are rerun in the authentication/security job
- RLS/owner-isolation contracts discover all `partgraph_app`-readable `user_id` tables, require FORCE RLS and owner policies on private owner tables, require no-owner-context reads to fail closed, prove transaction-local owner context does not leak, allow own-row updates while hiding another owner's row, and reject cross-owner inserts through `WITH CHECK`
- migration contracts require one Alembic head and one base, require every declared parent revision to exist, apply the complete migration history to an empty PostgreSQL database, verify the database is stamped at the exact current head, require every registered ORM table/column to exist in the migrated schema, and prove re-applying `upgrade head` is idempotent
- production-copy CI reconstructs `0020_catalog_coverage`, seeds representative persisted owner/session state, fingerprints baseline private columns without recording owner values, upgrades to current head, and requires every baseline row-count/digest fingerprint to remain unchanged
- live production-copy proof used Neon child branch `br-shiny-sunset-aebi1qvo` cloned from production `br-shiny-silence-aexgk2zm`; it started at `0020_catalog_coverage`, reached `0063_photo_storage_outbox`, and preserved all 18 baseline private-table fingerprints with zero mismatches; production itself was re-checked and remained at `0020_catalog_coverage`
- the live-copy SQL was emitted on validation commit `91a701e7229bf869bdc32aa488c7584b3a200e5a`; production-copy closeout commit `e81dd1659b4b5e2c7ea952b5d406313c2ce1ea51` differed from it only by removal of the temporary 14-line SQL-emission diagnostic, while current GitHub-green head `274fdd7d33d5b8d58759f52c9abe1bfe6ca4b988` additionally contains the later Phase 9 full-stack, verified-guidance, browser-E2E, service-worker runtime, randomized-acceptance, reference-fleet-acceptance, offline/degraded browser-validation, timeout/recovery proof, offline-pack logout-race fix, downstream-operation release gate, unsupported-computer-boundary proof, durable-photo outbox/hosted-backend validation, Blob OIDC credential support, the data-free source-code invariant, and the final RBAC authorization release gate
- the Neon validation branch is intentionally retained pending explicit branch-cleanup approval
- full-stack integration builds the locked React/Vite frontend with same-origin API configuration, packages `web/dist` into `api/partgraph/frontend`, migrates a fresh PostgreSQL database, starts FastAPI, proves the built JavaScript asset is served, proves database readiness, registers a real user with an HttpOnly session cookie, persists and rereads account preferences, creates and rereads a private Garage vehicle, logs out, and confirms the revoked session can no longer access `/api/v1/auth/me`
- browser automation is intentionally not claimed by the full-stack gate; DOM/browser E2E remains a later separate Phase 9 item
- verified-guidance integration creates reviewed OEM-style evidence and verified exact-applicability claims from the Civic oil-change reference dataset, materializes the repair through `partgraph_materializer`, registers an owner through HTTP, resolves the exact Civic configuration, creates and binds a repair session, proves readiness and ordered guidance are backed by verified claims from approved sources with immutable verified evidence, changes one current action's sole supporting claim to `needs_review` in the ephemeral validation database, requires guidance to fail closed with `REPAIR_PROCEDURE_INTEGRITY_ERROR`, restores the claim, and proves guidance recovers
- browser E2E installs pinned Playwright/Chromium only in the release-validation runner, builds and packages the real same-origin frontend, migrates PostgreSQL, starts FastAPI, creates an account through rendered controls, navigates Home → Settings → Garage, changes units through the visible settings card, verifies the visible success message and persisted Metric preference, logs out, explicitly switches from the retained registration tab back to Sign in, logs in again, verifies the persisted preference, and requires SPA navigation to move focus to the destination heading
- browser diagnostics fail on unexpected console/page errors after the intentional signed-out bootstrap; the browser run discovered that the built service worker was not served by the FastAPI runtime, so `api/partgraph/main.py` now serves `/sw.js` from the packaged frontend with `Cache-Control: no-cache`, and the final browser log confirms `/sw.js` returns HTTP 200
- randomized acceptance generates 20 deterministic synthetic cases from seed `20260917`; the cases cover 20 distinct synthetic makes, 20 distinct synthetic models, 20 distinct model years, at least eight trims, 1-4 required readiness items, 2-5 ordered actions, randomized readiness reconciliation order, ordered/unavailable recovery cases, and valid completed/skipped action paths
- every randomized case starts with synthetic evidence rather than real automotive facts, publishes exact identity and repair knowledge through the restricted materializer, binds a private owner repair session, proves initial inventory blocking, clears readiness, follows deterministic action order, reaches procedure completion, reaches `fully_mechanically_complete`, and verifies the expected immutable readiness/procedure event counts
- randomized acceptance is isolated to a freshly migrated disposable PostgreSQL CI service; it does not contact production, enable a provider, deploy application code, or publish synthetic knowledge outside that validation database
- reference-fleet acceptance creates another freshly migrated PostgreSQL service and reruns the authoritative reference runtime suites rather than copying their logic into a parallel test harness
- the reference-fleet job passed 10/10 runtime tests: Civic oil-change readiness/pause-resume/completion, Civic water-pump downstream completion, Civic systems/specifications, owner observation/photo round-trip, five photo-storage transaction/reconciliation contracts, and the generic Camry/F-150/Forester/Tucson fleet runner
- the separate permanent reference-runtime gate also passes independently on the exact head, providing an agreement check for the reference runtime boundary
- offline/degraded acceptance seeds reviewed Civic repair truth only in an ephemeral database, registers a real owner in Chromium, creates and binds a real repair session, and waits for the application to cache the versioned read-only repair pack in tab-scoped `sessionStorage`
- a synthetic database-readiness failure forces the authenticated repair workspace into the cached read-only view without changing the pack's last-sync timestamp; repair-state mutation controls remain unavailable while account logout is still allowed
- full Chromium network loss then renders the same cached repair state, and an actual page reload succeeds from the service-worker application-shell cache; the cached pack keeps the same server sequence, definition version, pack version, and last-sync timestamp rather than inventing new state
- Cache Storage is checked to ensure no `/api/` response is cached; the private repair pack remains out of durable `localStorage` and has owner identity fields stripped
- after reconnect, live server-backed Guided Repair returns and a freshly generated pack replaces the stale snapshot; confirmed logout clears the private offline pack
- timeout/recovery server proof forces the actual API platform boundary past a reduced test deadline and requires a structured retryable HTTP 504 with `REQUEST_DEADLINE_EXCEEDED`, request ID propagation, API version headers, and `Retry-After`
- commit-disconnect proof simulates PostgreSQL committing before its acknowledgement channel dies; PartGraph returns `DATABASE_WRITE_STATE_UNCERTAIN` only for a recoverable repair mutation carrying an idempotency key, then the recovery endpoint finds that exact committed event
- the browser proof sends one real pause mutation to the assembled application, lets it commit, discards the response, and requires the web client to recover the committed pause through the same idempotency key without resending the mutation
- the browser then receives a deadline response for a resume mutation before that write reaches the server; the client queries authoritative recovery state three times, does not blindly replay the mutation, surfaces `CLIENT_WRITE_STATE_UNCERTAIN`, and the server remains authoritatively paused
- the full regression campaign exposed an offline privacy race: a refresh already in flight during confirmed logout could complete after cache clearing and repopulate the private offline pack; `web/src/offline-repair.ts` now advances a cache epoch on auth-state clearing so stale pre-logout refreshes cannot write back
- the offline/degraded browser gate passes again with that race fix, confirming confirmed logout leaves the private offline pack cleared
- downstream-operation semantics reuses the authoritative canonical and runtime suites on a fresh migrated PostgreSQL database instead of duplicating downstream logic
- canonical downstream publication is append-only and idempotent, supported targets must belong to the same exact vehicle configuration, and only the dedicated materializer role can write canonical downstream truth while curator/app roles remain denied
- the Civic water-pump runtime proves completing `install-water-pump` activates `cooling.refill-air-bleed-after-water-pump`; the source repair becomes `downstream_required_pending` rather than mechanically complete
- merely creating the linked coolant repair does not satisfy the parent requirement; premature `linked_session_complete` resolution is rejected, and only after the linked refill/air-bleed repair itself reaches `fully_mechanically_complete` can the parent resolve to `fully_mechanically_complete`
- unsupported-computer acceptance uses synthetic verified evidence rather than invented real vehicle facts; its reserved terminal action is `boundary-computer-service-required`
- the boundary definition contract requires that reserved step to be terminal and non-skippable, while migrated database privilege tests prove `partgraph_app` and `partgraph_reviewer` can read but cannot mutate capability-boundary truth
- runtime proof completes the preceding physical action and then requires guidance status `unsupported_boundary`, `completion_allowed=false`, boundary code `computer_service_required`, and the fixed message that PartGraph does not support diagnostics, relearn, coding, programming, calibration, or service-tool operations
- attempts to mark that boundary `completed`, `skipped`, or `blocked` all fail with `REPAIR_PROCEDURE_ACTION_UNSUPPORTED_BOUNDARY`; no boundary progress row or event is persisted, and overall completion remains `unsupported_or_professional_pending` rather than `fully_mechanically_complete`
- durable-photo code-side validation passes local/private-backend contracts, image sanitization/security, the committed-before-side-effect outbox lifecycle, retry after ambiguous storage acknowledgement, tombstone-before-delete behavior, narrow NOLOGIN media-worker privileges, and both legacy Blob-token plus Vercel OIDC credential resolution
- the Vercel Preview probe deliberately removes its transient local cache before re-reading the object; on the exact head it fails before upload because the Preview environment has Vercel OIDC identity but no connected Blob store, so hosted durability remains explicitly pending instead of silently falling back to ephemeral `/tmp`
- the data-free invariant derives strong automotive facts and primary identity combinations from `api/data/reference` plus `api/data/reference_candidates` rather than maintaining a vehicle-name blacklist; adding/changing reference JSON therefore changes the guard automatically
- executable application, frontend, test, script, and CI source is scanned; reference-runtime tests now discover primary vehicle identity, manifests, candidate data and publication-plan paths through the generic data index rather than embedding the deep-reference vehicle's UUID, identity, engine, OEM facts, capacities, or vehicle-named directories
- clearly synthetic network/materialization/migration fixtures were changed to synthetic years/names/specification values where they never needed real vehicle facts
- the same invariant is also a permanent API CI check, not only a one-time Phase 9 job
- human RBAC contracts require the Blueprint hierarchy exactly: Owner has no curation authority; Contributor can submit but not review; Reviewer can review but not curator-publish; Curator can publish/resolve; only Operator/Admin can use operator-only authority
- the RBAC release job reruns operator last-admin/audit guardrails plus PostgreSQL privilege suites for ordinary app/shared reads, contributor staging-only writes, reviewer verification boundaries, curator claim/conflict authority, append-only materializer authority across repair/parts/vehicle domains/downstream truth, operator configuration authority, and read-only provenance/capability boundaries
- the human role hierarchy suite is also a permanent API CI contract, so role-set drift fails the normal API pipeline as well as Phase 9
- the first #189 attempt hit the already-known nondeterministic offline verifier assertion `offline reload invented a newer sync timestamp`; no RBAC or product code changed that path, and the same exact-head offline job passed on rerun, making #189 attempt 2 fully green
- all eight established exact-head regression workflows passed on `274fdd7d33d5b8d58759f52c9abe1bfe6ca4b988`: API #1080, Web #943, Extraction #417, Canonical Publication #354, Reference Repair Runtime #365, Database Reliability #204, Operational Observability #165, and Web Dependency Advisory #207

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

**Phase 9 is now in progress.** The five-model Phase 8 proof remains complete. Sixteen roadmap validation items are complete, including the new check that prevents real reference-vehicle facts from creeping back into executable source code. The GitHub final-validation workflow currently contains seventeen jobs because it also exercises the photo-storage implementation while the separate real hosted-photo proof remains open.

The current GitHub-green implementation/data commit is `b2e85d4d2cff1fd39c78c0e71c5d0dc7f252eed3`. All 17 jobs passed in MVP Final Validation CI #183, along with API CI #1077, Web CI #940, Extraction Pipeline CI #414, Canonical Publication CI #351, Reference Repair Runtime CI #362, Database Reliability CI #201, Operational Observability CI #162, and Web Dependency Advisory CI #204. The Vercel preview is intentionally **not** green on this head: the new photo probe found that Vercel supplies its normal OIDC identity but the project has no Preview Blob store connected, so PartGraph refuses to call ephemeral `/tmp` durable storage. The preview database schema remains `0059_primary_vehicle_domains`.

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

Hosted durable private-photo persistence is still pending at the environment level. The application now has durable outbox/retry handling, private Blob support, and Vercel OIDC credential support, but the Preview project still needs an actual private Blob store connected before the hosted round-trip can pass. The final regression campaign continues in Phase 9.

### Phase 2 — Survive network and timeout problems safely

The MVP policy here is complete. Offline repair use is read-only: already downloaded information can still be viewed, while writes remain server-authoritative.

Offline writing and reconciliation are not part of this MVP.

### Phase 3 — Keep private data and powerful actions separated

Functionally complete. Users, contributors, reviewers, curators, collectors, materializers, and operators have separate permissions. Owner Garage/session information remains private, while canonical automotive knowledge is shared but read-only to ordinary authenticated users.

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

**In progress.** Seventeen roadmap validation items are complete. All code-owned Phase 9 validation work is now green. The final-validation workflow has eighteen GitHub jobs: the prior release layers, code-side durable-photo contracts, data-free-source-code check, and RBAC authorization. Durable photo is still not marked complete because its separate real Vercel proof cannot run without a connected Preview Blob store.

The unit/domain layer checks fail-closed source authority, evidence-backed repair materialization, unsupported computer/service-tool boundaries, provider network safety, timeout hierarchy, ambiguous-write recovery, and vehicle-fact externalization. The API layer checks live/readiness health, request/version/security response headers, standardized 404/405 error envelopes, request-size enforcement, authenticated Garage and repair collection routing, and that the core repair API endpoints are actually exposed. The authentication/security layer checks unauthenticated rejection, CSRF and exact-origin enforcement, secure HttpOnly session cookies and HSTS, Argon2 password hashing, hashed session-token storage, logout revocation, matching invalid-credential responses for known and unknown identities, and persisted failed-login rate limiting through HTTP 429.

The owner-isolation layer checks the database itself instead of trusting application filters. It finds private tables that the normal application role can read, requires row-level security to be both enabled and forced, verifies each owner policy uses the transaction-local `partgraph.user_id` context, proves that missing owner context reveals nothing, proves one user's context cannot see or update another user's row, proves the context disappears after the transaction, and rejects attempts to insert a row for a different owner.

The migration layer validates the migration history itself and then builds a completely empty PostgreSQL database to the current head. It requires one current head and one base, checks that every migration parent exists, confirms every registered application table and column is present after the upgrade, confirms the Alembic revision stamp is exact, and confirms running the head upgrade again makes no further migration change.

The production-copy layer goes further. The permanent CI job starts from the actual production-era revision `0020_catalog_coverage`, seeds persisted owner/session data, fingerprints the baseline private columns without storing private values, upgrades to current head, and proves the fingerprints are unchanged. We then repeated that against a real isolated Neon child of production: the copy upgraded from `0020_catalog_coverage` to `0063_photo_storage_outbox`, all 18 private-table fingerprints matched exactly before and after, and production itself remained untouched at `0020_catalog_coverage`. The validation branch is being kept until branch cleanup is explicitly approved.

The full-stack layer proves that the frontend and backend are not merely passing tests in isolation. CI builds the real React/Vite bundle, places it where FastAPI serves production-style frontend files, migrates PostgreSQL, starts the assembled application, fetches the built JavaScript asset, verifies API/database readiness, creates a real user session, saves and rereads account preferences, creates and rereads a Garage vehicle, and logs out. This is HTTP/runtime integration only; browser clicking and DOM behavior remain for the separate browser-E2E task.

The verified-guidance layer proves the trust chain that matters most for repair instructions. Reviewed OEM-style evidence becomes verified exact claims, only the restricted materializer can turn those claims into the canonical repair, the owner then reaches that repair through the normal exact-vehicle/session HTTP path, and every guidance action is checked against its current supporting evidence. The test deliberately moves the current action's supporting claim back to `needs_review`; guidance immediately fails closed instead of serving stale instructions, then recovers after the verified claim is restored.

The browser layer now proves what a person actually sees and clicks. A real Chromium browser creates an account, navigates between Home, Settings, and Garage, changes units using the visible control, checks that the setting survives logout and login, and verifies that keyboard/browser focus follows SPA navigation. It also caught a real deployment problem that HTTP-only tests missed: the built service worker existed but FastAPI did not serve `/sw.js`. That route is now part of the packaged runtime and the final browser run receives HTTP 200 instead of 404. Expected signed-out session detection is allowed during bootstrap, but unexpected browser console or page errors after that still fail the gate.

The randomized layer is deliberately synthetic so it can stress runtime behavior without pretending invented automotive facts are real. Using fixed seed `20260917`, it creates 20 different synthetic year/make/model/trim configurations, varies repair requirements and action counts, changes the order in which readiness is satisfied, exercises ordered/unavailable recovery, and includes valid skipped actions. Every case still goes through the actual trust/publication boundary, private owner session, readiness blockers, deterministic next-action logic, event history, and final completion rules. All 20 passed, and because the seed is fixed the exact case set can be reproduced if a future change breaks one.

The reference-fleet layer uses the real reviewed reference data rather than synthetic vehicles. On a new migrated database it reruns the Civic oil-change path, the water-pump plus required coolant follow-on path, Civic structure/specifications, owner observation/photo behavior, the photo-storage transaction and reconciliation protections, and the generic Camry/F-150/Forester/Tucson runner. Ten runtime tests passed. This final-validation result also matches the separate permanent Reference Repair Runtime CI on the same commit, so the fleet proof is not dependent on only one workflow.

The offline/degraded layer proves the current MVP's deliberately conservative offline design. While online, the browser caches a server-confirmed, versioned repair snapshot in tab-only storage. When the API becomes degraded, PartGraph shows that last confirmed repair as read-only instead of guessing. When Chromium is taken completely offline, the same repair remains available and the page can be reloaded from the cached public application shell. The service worker does not cache private API responses, the repair pack does not contain owner identity fields, and no offline repair-step buttons appear. Reconnecting returns the browser to live Guided Repair and refreshes the snapshot from the server; confirmed logout removes the private cached pack. During this round of regression testing, the browser caught a real race where an older offline-pack request could finish after logout and refill the cache. PartGraph now invalidates pre-logout refreshes, and the offline gate is green again.

The timeout/recovery layer proves what PartGraph does when a write result is uncertain. The server has a shorter deadline than the browser and external providers have a still smaller budget. A simulated database commit followed by acknowledgement loss is labeled uncertain rather than failed. In the browser, a pause request is allowed to commit and then its response is deliberately lost; PartGraph checks the recovery endpoint with the same idempotency key and correctly shows the committed paused state without sending the pause twice. A later resume receives a deadline response before the write reaches the server; PartGraph checks the server repeatedly, does not retry the mutation, tells the user the write state cannot be confirmed, and leaves the authoritative repair state paused.

The downstream-operation layer proves the rule at the center of PartGraph: replacing the part is not automatically the end of the repair. Canonical downstream rules must come from verified evidence and can be written only through the restricted materializer. The target repair must belong to the same exact vehicle. In the Civic water-pump case, installing the pump activates the required coolant refill and air-bleed work. PartGraph keeps the water-pump repair incomplete even after every water-pump UI action is finished. Starting the coolant repair is still not enough; that linked repair must actually finish its required physical actions before the parent repair can finally say it is mechanically complete.

The unsupported-computer layer proves the other hard boundary. A synthetic repair completes its ordinary physical step and then reaches a required computer/service-tool step. At that point PartGraph says the step is unsupported: it cannot be marked complete, skipped, or treated as an ordinary blocked action. No fake progress is saved, and the repair cannot claim full mechanical completion. The test explicitly covers diagnostics, relearn, coding, programming, calibration, and service-tool work without pretending PartGraph can perform them.

The photo-storage code is now tested much more deeply. PartGraph records the photo payload and storage intent durably before the outside storage write, can retry safely after an uncertain storage result, deletes through a durable tombstone, restricts the media worker, sanitizes uploaded images, and supports Vercel's rotating OIDC identity. The real hosted proof is intentionally still red because the Preview project has no Blob store connected. That missing cloud resource is why the durable-photo checkbox stays open.

The data-free check is complete. Instead of keeping a handwritten list of reference-fleet facts, the test reads the reference JSON itself and turns those facts into the guard. It scans executable application/frontend/test/script/CI source and fails if strong reference facts or a recognizable reference identity combination have leaked into code. Existing deep-reference tests were refactored to discover the selected vehicle and dataset paths from a generic data index, while unrelated network and migration tests use clearly synthetic vehicles and values.

The RBAC layer is complete. It checks the five human roles directly: Owner cannot enter contribution/review/curation/operator gates; Contributor can submit candidate evidence but cannot review; Reviewer can review but cannot perform curator-only publication; Curator can publish and resolve conflicts; Operator/Admin is the only operator-only role. The same job then reruns the database privilege boundaries so an application-role mistake cannot silently grant staging, review, canonical-write, materializer, or operator power. Operator role changes remain audited and the last active operator cannot be demoted.

All 18 GitHub jobs passed in MVP Final Validation CI #189 attempt 2 on `274fdd7d33d5b8d58759f52c9abe1bfe6ca4b988`, and all eight established exact-head regression workflows also passed. Attempt 1 had only the previously known timing-only offline timestamp assertion; the same exact-head offline job passed on rerun. **There is no remaining code-owned Phase 9 validation task. Hosted durable photo persistence is the sole Phase 9 blocker until the Preview Blob store is connected.**

### Phase 10 — Move the finished MVP into production

Not started and still requires explicit production approval. The eventual cutover must use one exact green commit, synchronized frontend/backend code, validated schema changes, health checks, real owner-state checks, and production-safe smoke tests. Unreviewed automotive data will not be seeded as canonical truth.

### Safety rules that remain in force

Updating this tracker does **not** authorize merging PR #84, migrating production, enabling production collectors/providers, deleting Git or Neon branches, weakening source authority, or skipping human evidence review.

If information is missing, PartGraph keeps it missing instead of guessing. If trusted sources disagree, the conflict remains explicit until reviewed. AI or candidate data cannot publish itself as canonical automotive truth.

Charm.li approval remains narrow: manually reviewed evidence for the approved 2009 Civic Hybrid water-pump and physical coolant refill/air-bleed MVP path only. Automated Charm.li collection remains disabled.

### Exact place to resume work

Phase 9 is in progress. **All code-owned Phase 9 validation tasks are complete. Durable photo persistence is the only remaining Phase 9 item and is externally blocked on connecting a private Blob store to Vercel Preview; after that connection, rerun the hosted durable-photo probe and exact release matrix before Phase 10.**

The separate Phase 6 live NHTSA HTTP-ingestion proof and broad repair-knowledge work, Phase 1 hosted durable-photo proof, remaining Phase 9 validation campaign, and production cutover requirements all remain pending in their existing roadmap locations.