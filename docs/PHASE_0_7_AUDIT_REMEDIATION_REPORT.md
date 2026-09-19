# PartGraph Phase 0–9 Audit and Remediation Register

Original audit date: 2026-09-15  
Phase 8–9 re-audit date: 2026-09-19  
Scope: repository, consolidation preview, production boundary, database state, CI/CD, runtime behavior, frontend/browser/accessibility, data lifecycle, security, reliability, and roadmap state through completion of Phase 9.  
Implementation fixes performed during the original 2026-09-15 audit: **none**. Phase 8–9 re-audit remediation is recorded inline below as each eligible item is completed.  
Post-audit remediation updates are recorded inline when an entire issue category is completed.  
Explicit audit exclusion: sign-in/sign-up mechanics themselves were not reviewed; authorization, ownership, isolation, secrets, trust boundaries, and operator access were reviewed.

## Purpose

This file is the durable technical handoff for the original five-pass Phase 0–7 audit plus the Phase 8–9 remediation re-audit. It is intentionally organized by problem domain rather than audit pass so a future implementation session can fix one bounded issue at a time without reconstructing chat history.

For every item, preserve the PartGraph architecture contract:

- application code contains behavior; automotive facts belong in reviewed data/evidence
- missing means missing; conflicts stay explicit
- AI/candidate data cannot self-publish canonical truth
- reference vehicles are validation data, never vehicle-specific runtime branches
- computer/service-tool programming, coding, relearn, initialization and calibration remain non-completable unless policy/evidence changes explicitly
- physical/mechanical work such as verified bleeding may be supported
- historical deployed migrations must remain immutable; cleanup must be forward-only
- PR #84 must not be merged, production migrated, providers activated, source authority weakened, human review bypassed, or branches/data deleted without explicit authorization

## Original Phase 0–7 audited state snapshot

At the end of the audit:

- `main` before this report: `250cf24ad90e16bb42c076095c5db5c834bcf036`
- consolidation branch: `partgraph-mvp-consolidation`
- consolidation head: `0a6918c800d5580b463b9e07a65370662c367ecb`
- last implementation/data proof commit: `7b1d7df912bdc5749cad46efee771f97c5a20107`
- PR #84: open, draft, unmerged
- consolidation preview schema: `0059_primary_vehicle_domains`
- production schema: intentionally still `0020_catalog_coverage`
- Phase 7: complete
- Phase 6: still in progress because broad repair-knowledge population and deployed NHTSA HTTP-ingestion proof remain pending
- Phase 1 hosted durable-photo persistence proof: still pending
- current consolidation preview persisted counts observed during audit: 364 vehicle configurations, 282 verified evidence rows, 282 MechanicalClaims, 267 part fitments, 1 repair definition, 5 repair sessions, 0 persisted vehicle-structure rows, 0 persisted vehicle-specification values, 0 persisted repair-photo rows
- the absence of structure/specification rows in the long-lived preview is intentional non-seeding, not a Phase 7 failure; fresh-database materialization tests prove those domains

## Phase 8–9 re-audit update — 2026-09-19

**Status: RE-AUDITED THROUGH PHASE 9 on `partgraph-mvp-consolidation`; remediation remains bounded by the execution-status overlay.**

Current proof boundary:

- consolidation head audited: `5a95001b594e14437492dd131d41f519619a0eff`
- Phase 8 five-model reference-fleet proof: complete
- Phase 9 final MVP validation: complete
- MVP Final Validation CI #205: all 18 jobs passed on the exact clean head
- all eight established exact-head regression workflows also passed on that head
- exact-head Vercel Preview `dpl_7qkpKhUL7Yui3rT3Npvwg8kh3PCN`: READY
- hosted private-photo persistence proof: passed real private Blob write → transient-cache deletion → Blob re-read/byte verification → deletion
- production database: intentionally unchanged at `0020_catalog_coverage`
- PR #84: still draft/unmerged
- Phase 10 production cutover: not started and still requires explicit authorization
- Phase 6 deployed NHTSA HTTP proof and broad repair-knowledge population: still pending

The execution-status convention remains authoritative:

- `COMPLETE`
- `ELIGIBLE`
- `BLOCKED`
- `BACKLOG`
- `CURRENT CONTROL COMPLETE / FUTURE BACKLOG`

A `BLOCKED` or `BACKLOG` classification wins over audit priority. Later-phase or infrastructure-dependent work is not pulled forward merely because it is P1/P2.

### Phase 8–9 status reassessment

The Phase 9 implementation materially changes several old dependency decisions:

- `PG-AUD-REL-003`: current serverless connection control is proven with a 24-parallel-instance `NullPool` database connection test; future higher-scale/pooler validation remains future backlog.
- `PG-AUD-UI-006`: current SPA navigation focus/title behavior is now exercised by the real Chromium Phase 9 browser gate.
- `PG-AUD-CODE-003`: complete. `YearWheel.tsx` and `production-launch.css` are removed and guarded by `web/scripts/validate-retired-frontend-assets.mjs`.
- `PG-AUD-UI-011`: complete because the unused custom YearWheel was retired rather than carried into production.
- `PG-AUD-ROAD-001`: complete. Hosted durable private-photo persistence now passes on the real Vercel Preview with the private Blob store connected.
- `PG-AUD-TEST-001`: complete for the Blueprint Phase 9 release layers: unit/domain, API, auth/security, RLS/owner isolation, migrations, production-copy migration, full-stack, verified guidance, browser E2E, randomized acceptance, reference-fleet acceptance, offline/degraded behavior, timeout/recovery, downstream semantics, unsupported-computer boundary, durable photo, data-free-source-code, and RBAC all have permanent Phase 9 jobs.
- `PG-AUD-CODE-001`: `COMPLETE` on remediation head `a1c868b39bc2ff6044093a172a761a2d5883df68`. The legacy `partgraph.auth`, `partgraph.user_vehicle`, `partgraph.repair_definition`, and `partgraph.repair_experience.repair_session` bridge packages were removed only after remaining consumers were migrated to canonical `identity`, `knowledge`, and `repair_experience` modules. An AST-based CI guard now rejects reintroduction of either the retired packages or imports resolving to them.
- `PG-AUD-CODE-004`: `COMPLETE` on remediation head `3bc78cf918cd9957beab0597b30c17da6f7b841f`. The permanently hidden Readiness session/lease subtree, dead handlers, and stale CSS were removed; visible edit-control ownership remains in Overview/Guided Repair. The existing retired-frontend guard now prevents the hidden controls from returning.
- `PG-AUD-UI-008` and `PG-AUD-UI-009`: remain `BACKLOG` as post-MVP browser/accessibility hardening. Phase 9 intentionally proves real Chromium behavior, but the repository still has no declared multi-browser support matrix, Firefox/WebKit CI, axe-style automated accessibility scan, or manual screen-reader release evidence.
- `PG-AUD-REL-001`, `PG-AUD-REL-007`, `PG-AUD-DEP-001`, and `PG-AUD-DEP-003`: remain `BLOCKED` because their remaining acceptance depends on production infrastructure, alert delivery, Phase 10 cutover, or an explicit repository-governance decision.
- `PG-AUD-ROAD-002` and `PG-AUD-ROAD-003`: remain `BACKLOG` because they are still genuine unfinished Phase 6 roadmap work.

### Newly observed Phase 9 closeout finding

`PG-AUD-DEP-005` was added below: documentation-only commits to `main` currently trigger Vercel Production builds. The observed Phase 9 roadmap closeout commit changed only `docs/ROADMAP_LIVE.md`, yet Vercel automatically produced a READY Production deployment. No application code or production schema changed, but the deploy trigger is broader than the intended production-change boundary. This finding is `BLOCKED` pending explicit production/deployment-governance authorization.

---

## Confirmed controls that should not be weakened

These are not remediation tasks. They are working controls that future changes must preserve.

- vehicle make/model discovery is provider/data-driven rather than a make whitelist
- no active runtime branch such as `if vehicle == "2009 Honda Civic Hybrid"` was found
- the primary Civic mechanical/reference facts are externalized under `api/data/reference/...`
- exact vehicle applicability, evidence, authority policy, human review, conflict quarantine and restricted materializers govern canonical publication
- contributor/reviewer/curator/materializer privileges are separated
- ordinary users cannot directly write canonical mechanical truth
- PostgreSQL row-level security is enabled and forced on private owner/repair tables inspected in the live preview
- application/pipeline database roles are `NOLOGIN`, non-superuser, and cannot bypass RLS
- VIN storage uses authenticated encryption with owner-bound associated data and a user-scoped lookup fingerprint
- provider credentials are encrypted, provider-bound and key-versioned; plaintext credentials are not serialized back to the operator UI
- NHTSA acquisition currently uses a fixed `https://api.nhtsa.gov/...` collector endpoint rather than blindly dereferencing arbitrary configured provider URLs
- source license/approval/automation state is re-evaluated when ingestion runs
- repair mutations use idempotency keys, per-session locking and authoritative write-recovery endpoints
- repair event history is append-oriented and projections are rebuildable
- ambiguous browser timeout/network outcomes are not blindly replayed; unresolved outcomes become `CLIENT_WRITE_STATE_UNCERTAIN`
- offline repair mode is intentionally read-only and server-authoritative
- the service worker does not cache `/api/` responses
- the nginx/container web path has a CSP and CI asserts it
- API errors use controlled envelopes/request IDs rather than exposing raw stack traces
- current preview inspection found no persistent lock/stalled-query condition
- the approved Charm.li service-manual mirror evidence remains `licensed_oem_derived`, manually reviewed for the narrow MVP path, with `automation_allowed=false`

---

# A. Data model, schema and canonical-data integrity

## Category A remediation update — 2026-09-15

**Status: COMPLETED on `partgraph-mvp-consolidation`; not cut over to `main` application code or production.**  
Category A proof head: `9946b373a32d44963e6fd8fcc838653473bd471a`.  
Consolidation preview schema after cleanup: `0061_retire_legacy_specs`.  
Production remains intentionally at `0020_catalog_coverage`; PR #84 remains open/draft/unmerged.

All six Category A findings have been remediated on the consolidation branch:

- `PG-AUD-DATA-001`: ORM claim-domain metadata, source-policy domains and Alembic schema are aligned and guarded by schema-alignment tests.
- `PG-AUD-DATA-002`: the operational equipment catalog now loads from the versioned `api/data/equipment/equipment_catalog_v1.json.gz` dataset through `catalog_dataset.py`; deterministic seeding reads that dataset rather than executable catalog-generation logic. Legacy generator modules are not the operational catalog source and remain a later dead-code/maintainability concern rather than runtime data authority.
- `PG-AUD-DATA-003`: persistent publication is now governed by `persistent_publication_plan_v1.json`, `docs/CANONICAL_PUBLICATION_RUNBOOK.md`, and a permanent Canonical Publication CI contract. Deployment remains separate from automotive-truth publication; no preview/production publication was performed as part of this remediation.
- `PG-AUD-DATA-004`: forward migration `0061_retire_legacy_spec_observations.py` retires the five pre-modern verified specification observations with fail-closed lineage/dependency checks. Current preview count of legacy verified specification candidates is zero.
- `PG-AUD-DATA-005`: forward migration `0060_retire_selected_asian_workbook.py` removes the orphaned workbook staging/configuration/coverage lineage with dependency assertions while preserving immutable historical migrations. Current preview workbook configuration, workbook staging and unverified coverage counts are all zero.
- `PG-AUD-DATA-006`: the duplicate `docs/Selected_Asian_Brands_1996_2000.xlsx` and unused `api/data/archive/reference_fleet_legacy/` JSON assets were removed after dependency proof. The single `api/data/Selected_Asian_Brands_1996_2000.xlsx` copy remains intentionally because immutable migrations 0017/0020 still require that path for historical reconstruction. `api/data/README.md` documents the exception and `test_reference_fixture_externalization.py` prevents duplicate/archive regression.

Exact final proof on `9946b373...`: API CI/CD #840, Web CI/CD #703, Extraction Pipeline CI #138, Canonical Publication CI #104 and Reference Repair Runtime CI #83 all passed. Fresh migration execution, persisted-history upgrade checks, canonical materialization, reference repair runtime and the repository-data hygiene assertions all remained green.

The original issue statements below are retained as the audit baseline that motivated the remediation.

## PG-AUD-DATA-001 — SQLAlchemy MechanicalClaim domain constraint is stale

**Priority:** P1  
**Type:** schema drift / correctness

**Problem:** `api/migrations/versions/0059_primary_vehicle_domains.py` expands `mechanical_claims.claim_domain` to seven domains, adding `vehicle_structure` and `vehicle_specification`. `api/partgraph/knowledge/source_policy.py` also understands those domains. However `api/partgraph/knowledge/models.py` still declares `ck_mechanical_claims_domain` with only the original five domains (`vehicle_identity`, `safety_campaign`, `repair_requirement`, `repair_procedure`, `part_fitment`).

The deployed database works because Alembic owns the actual schema, but SQLAlchemy metadata is no longer an exact description of the live schema. This can mislead autogeneration/schema-diff tooling, break metadata-created test databases, and create future migration errors.

**Proposed solution:** update the ORM constraint to the same seven-domain contract as migration 0059. Add a test that compares the ORM constraint/domain set to the migration/current source-policy domain set so the three cannot drift independently.

**Acceptance criteria:** ORM metadata, Alembic head and source-policy domain matrix all recognize exactly the same supported claim domains; metadata-created test schema accepts structure/specification claims; no historical migration is edited.

---

## PG-AUD-DATA-002 — Generic equipment/inventory product data is embedded in Python

**Priority:** P1/P2  
**Type:** architecture debt / data hardcoding

**Problem:** substantial generic catalog data lives in executable Python rather than a versioned data layer. Relevant files include:

- `api/partgraph/equipment/catalog_seed_v1.py`
- `api/partgraph/equipment/inventory_catalog_v2.py`
- `api/partgraph/equipment/manual_reference_v1.py`

The embedded content includes tool/socket/wrench families, oil grades/formulations, coolant chemistries, washer-fluid categories, lug-nut thread sizes, aliases, retired keys, service equipment and other inventory records. The preview contained 1,178 equipment catalog rows during audit.

This is not vehicle-specific repair truth, so it does not violate the core vehicle-hardcoding invariant in the same way as embedding an OEM torque or part number would. It is still operational product data compiled into application code, making review/versioning/removal harder and increasing the chance that data changes are treated as code behavior.

**Proposed solution:** move catalog rows to a versioned dataset format (JSON/CSV/other explicit catalog artifact), validate it with a schema, import/upsert it through a deterministic catalog loader, and keep only normalization/validation behavior in Python.

**Acceptance criteria:** changing a catalog item does not require editing Python business logic; catalog version/checksum is explicit; seed/import is idempotent; retired-key behavior is represented in the dataset or a narrowly defined migration policy.

---

## PG-AUD-DATA-003 — Persistent-environment canonical publication policy is implicit

**Priority:** P2  
**Type:** environment parity / operational data lifecycle

**Problem:** Phase 7 correctly proves structure/specification and three reference repairs through fresh-database materialization, while the long-lived preview intentionally remains non-seeding. During audit the preview had one persistent repair definition and zero persistent structure/specification rows even though the repo contains the three approved repair datasets and reviewed structure/specification evidence.

This is not a failed Phase 7 implementation. The problem is that the production/cutover policy for **which reviewed facts are deliberately published into a persistent environment and when** is not yet a single explicit promotion procedure.

**Proposed solution:** define a canonical-publication runbook that names the reviewed datasets/claims to publish, required role, evidence/authority preconditions, expected row/version counts, idempotency rules, post-publication verification queries and rollback/supersession behavior. Keep deployment and publication separate: deploying code must not silently seed canonical automotive truth.

**Acceptance criteria:** an operator can state exactly which reference knowledge exists only as fixtures/tests versus which is intentionally canonical in preview/production; a publication run produces deterministic expected records and evidence links without deployment-time seeding.

---

## PG-AUD-DATA-004 — Five legacy specification candidates are marked verified outside the modern evidence chain

**Priority:** P2  
**Type:** legacy provenance debt

**Problem:** the preview contains five old `vehicle_specification_candidate` staging rows with `review_status='verified'` but no corresponding `catalog_verified_evidence` rows. They predate the current evidence → MechanicalClaim → canonical materialization path and represent roughly 9.7 KiB of logical row payload.

Leaving them indefinitely makes the word “verified” mean two different things: old staging review state versus modern immutable verified evidence.

**Proposed solution:** inspect the five facts. If any manufacturer-backed fact is still needed, reintroduce it through the modern registered-source/immutable-evidence/claim pipeline. Once equivalent modern provenance exists—or the old fact is no longer needed—remove the legacy staging artifacts with a forward cleanup operation.

**Acceptance criteria:** no staging-only legacy row is treated as canonical merely because an old `review_status` says verified; retained facts have modern evidence lineage; cleanup does not rewrite historical migrations.

---

## PG-AUD-DATA-005 — Selected Asian workbook lineage is orphaned live database data

**Priority:** P2  
**Type:** database cleanup / legacy data

**Problem:** migration-era workbook data remains live even though it has no downstream product dependency. Audit dependency checks found:

- 363 pending workbook staging identity rows
- 363 unverified `vehicle_configurations`
- 363 associated unverified coverage rows
- one ingestion-batch row and one coverage-batch row
- zero `user_vehicle` references
- zero repair-definition references
- zero MechanicalClaim references
- zero fitment references

The 363-row workbook was explicitly breadth/proof data with no retained per-row authoritative citation. Strong cleanup candidate total: **1,091 rows, approximately 695 KiB logical row payload**.

**Proposed solution:** create a forward cleanup migration/script that identifies the exact legacy workbook lineage by stable batch/source identifiers, asserts zero external dependencies, deletes only those live rows in FK-safe order, and records the cleanup. Do not edit migrations 0017/0020 because deployed migration history must remain immutable.

**Acceptance criteria:** all orphaned workbook-lineage rows are gone, current canonical/reference records remain untouched, dependency assertions run before deletion, historical migrations are byte-for-byte unchanged.

---

## PG-AUD-DATA-006 — Duplicate/archive repository data needs dependency-proven cleanup

**Priority:** P3  
**Type:** repository hygiene

**Problem:** the same workbook blob exists in both:

- `api/data/Selected_Asian_Brands_1996_2000.xlsx`
- `docs/Selected_Asian_Brands_1996_2000.xlsx`

Git deduplicates identical blobs internally, but working trees contain two copies. Legacy archive datasets also remain under `api/data/archive/reference_fleet_legacy/` (`reference-fleet-v1.json`, `repair-corpus-v1.json`).

**Proposed solution:** build an import/reference dependency map first. Remove one workbook copy and archive assets only after proving no migration, test, script or documentation workflow reads the path. Preserve anything required to reconstruct historical migrations/tests.

**Acceptance criteria:** no duplicate working-tree asset without a documented reason; no broken migration/test/import path after cleanup.

---

# B. Security and trust boundaries

## PG-AUD-SEC-001 — Hosted Vercel path has no Content-Security-Policy

**Priority:** P1  
**Type:** browser security / deployment parity

**Problem:** the nginx/container path sends a CSP and Web CI verifies it, but the audited Vercel preview did not send `Content-Security-Policy`. It did send HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, referrer policy and permissions policy. The result is security-header drift between the tested container and the actual hosted serverless path.

This matters because the hosted page executes JavaScript, may include Vercel toolbar/feedback scripts, and PartGraph keeps an offline repair pack in browser storage.

**Proposed solution:** define the CSP at the HTTP layer that actually serves Vercel responses (FastAPI middleware and/or supported Vercel header configuration), accounting for any required Vercel preview tooling. Add a deployed-header smoke check rather than testing only nginx.

**Acceptance criteria:** production and preview hosted responses include the intended CSP; no inline/eval script allowance is introduced casually; required application behavior still works; a CI/deployment probe fails if CSP disappears.

---

## PG-AUD-SEC-002 — Fresh preview operator bootstrap is “first authenticated user wins”

**Priority:** P1  
**Type:** authorization bootstrap risk

**Problem:** the preview bootstrap is narrowly gated to the intended Vercel preview/branch and becomes unavailable after an operator administrator exists. The current preview already has an active operator, so this is not an active takeover route there. On a newly created/reset publicly reachable preview with no operator, however, the first authenticated user able to invoke the bootstrap can become `operator_admin`.

**Proposed solution:** require an explicit bootstrap authority: one-time secret, predetermined operator identity, out-of-band administrative initialization, or deployment access protection until bootstrap completes. Preserve the existing audit event.

**Acceptance criteria:** an arbitrary authenticated account cannot claim operator administration solely because it arrived first at a fresh preview; bootstrap is single-use/audited and fails closed.

---

## PG-AUD-SEC-003 — Operator configuration writes use the general application database role

**Priority:** P2  
**Type:** least privilege

**Problem:** operator HTTP routes enforce operator-admin authorization and CSRF correctly, but the generic `partgraph_app` database role still has mutation privileges on some provider/source configuration tables. A future application-layer authorization/injection defect would therefore have a larger database blast radius than necessary.

**Proposed solution:** introduce a dedicated `partgraph_operator` NOLOGIN role with only required provider/source/operator-table privileges. Authorized operator requests should `SET LOCAL ROLE partgraph_operator`; normal owner requests remain under `partgraph_app`. Keep source-authority-policy and canonical publication permissions separately restricted.

**Acceptance criteria:** normal `partgraph_app` cannot mutate operator/provider configuration; operator endpoints can do so only after explicit role transition; database privilege tests cover allow/deny cases.

---

## PG-AUD-SEC-004 — Generic provider URLs need SSRF protection before becoming executable

**Priority:** P2  
**Type:** future connector security / SSRF

**Problem:** generic provider configuration accepts `http://` or `https://` base URLs. The current NHTSA collector is safe from this specific problem because it fetches a fixed `api.nhtsa.gov` endpoint and separately validates NHTSA binding semantics. Future generic adapters that dereference stored `base_url` values could reach loopback/private/link-local/cloud metadata addresses or follow dangerous redirects.

**Proposed solution:** before any generic provider URL becomes executable, add URL normalization and network policy that rejects userinfo, loopback, RFC1918/private ranges, link-local, metadata endpoints, unsafe redirects and DNS resolution/rebinding to private addresses. Prefer explicit hostname allowlists for high-trust provider adapters.

**Acceptance criteria:** provider tests prove forbidden internal targets cannot be reached directly or via redirects/DNS changes; existing fixed NHTSA behavior remains unchanged.

---

## PG-AUD-SEC-005 — Photo validation stops at signature/header recognition

**Priority:** P2  
**Type:** uploaded-file hardening

**Problem:** repair photos already have strong owner/path/private-storage controls, a 4 MiB ceiling, controlled storage keys and byte-based type recognition. They are not fully decoded before storage. A malformed/polyglot/decompression-bomb-like image can therefore pass a leading-signature check even if it is not a healthy supported image.

**Proposed solution:** fully decode with a maintained image library, enforce pixel/dimension/decompression limits, reject malformed images, optionally normalize/re-encode to a controlled format, and strip EXIF/GPS metadata unless explicitly required.

**Acceptance criteria:** malformed/truncated/oversized-dimension/decompression-bomb fixtures are rejected; valid supported images survive; privacy-sensitive metadata is handled by explicit policy.

---

## PG-AUD-SEC-006 — GitHub Actions permissions and action references are broader/weaker than necessary

**Priority:** P2  
**Type:** CI supply-chain security

**Problem:** specialized extraction/publication/reference workflows are largely read-only, but API/Web workflows grant `packages: write` at workflow scope even when only publishing jobs need it. Actions are referenced by floating major tags such as `actions/checkout@v7` rather than immutable commit SHAs.

**Proposed solution:** set top-level permissions to read-only and grant `packages: write` only on image-publish jobs. Pin third-party actions to full commit SHAs and use Dependabot/Renovate (or an equivalent controlled process) to update pins.

**Acceptance criteria:** build/test jobs cannot publish packages; action code is immutably pinned; CI remains green.

---

## PG-AUD-SEC-007 — Offline repair pack stores more plaintext identity data than needed

**Priority:** P3  
**Type:** browser-data minimization

**Problem:** the read-only offline pack uses `sessionStorage`, which is safer than persistent local storage and is cleared with auth-state loss, but it includes owner identity/email/username plus vehicle/repair state. Any same-origin script executing after an XSS can read it.

**Proposed solution:** remove owner email/username and any field not required to render/reconcile offline repair state. Keep the pack tab/session scoped until a deliberate encrypted/persistent offline architecture exists. Treat CSP as a primary compensating control.

**Acceptance criteria:** offline continuity works with the minimum private fields required; no unnecessary personally identifying fields are stored.

---

## PG-AUD-SEC-008 — Web dependency advisory scan may fail open during prolonged registry outage

**Priority:** P3  
**Type:** release security assurance

**Problem:** Web CI retries `npm audit`, then explicitly continues if the advisory endpoint stays unavailable. That is reasonable for CI availability but means a particular release can be built without a successful current advisory result.

**Proposed solution:** retain transient-outage tolerance, but add an independent scheduled advisory scan or release condition requiring a recent successful high-severity dependency scan.

**Acceptance criteria:** a temporary registry outage does not deadlock all development, but production release cannot indefinitely proceed with no recent successful security scan.

---

# C. Reliability, recovery and durable state

## PG-AUD-REL-001 — Production database disaster-recovery posture is inadequate

**Priority:** P1  
**Type:** disaster recovery / data durability

**Problem:** at audit time the Neon project exposed zero snapshots, only about six hours of history retention, and an unprotected production branch. No repository workflow periodically backs up production owner data or proves a restore. Once PartGraph stores real garage/repair/photo metadata, this is insufficient.

**Proposed solution:** define explicit RPO and RTO, protect production, extend point-in-time/history retention to a suitable window, add snapshot/export protection as supported, and run documented restore drills against a disposable recovery target. Alert on loss of backup/retention protection.

**Acceptance criteria:** documented RPO/RTO exist; production protection is enabled; a recent restore drill proves owner/repair data can be recovered; backup status is observable.

---

## PG-AUD-REL-002 — Photo blob/file operations and PostgreSQL commits can split-brain

**Priority:** P1  
**Type:** cross-system atomicity

**Problem:** photo creation stores the external blob/file before the surrounding DB transaction finally commits. A later commit failure can leave an orphan blob. Photo deletion removes external content before the DB deletion state finally commits; a later DB failure can leave metadata pointing at missing content. In-method compensation cannot observe a transaction commit failure that occurs after the service returns.

**Proposed solution:** adopt a durable finalization/outbox pattern. Commit desired metadata/state first, then finalize/delete external storage through an idempotent worker/action, or use a two-state record (`pending`/`ready`/`delete_pending`) plus reconciliation. Add periodic orphan/missing-object reconciliation.

**Acceptance criteria:** simulated DB commit failures cannot permanently create an untracked blob or a live DB record whose object is gone; retries are idempotent; reconciliation has tests.

---

## PG-AUD-REL-003 — Serverless deployment can multiply direct PostgreSQL pools

**Priority:** P2  
**Type:** scaling / connection management

**Problem:** the API uses a normal SQLAlchemy pool (roughly ten possible connections per process with configured pool/overflow), while Vercel may start multiple serverless instances. The audited Neon endpoint did not use its pooler. Instance multiplication can exhaust database connections well before CPU/request capacity.

**Proposed solution:** choose and document a serverless database strategy: use the appropriate Neon pooled endpoint/transaction-pooling configuration or deliberately use a very small/no persistent client pool compatible with serverless lifecycle. Load-test concurrent cold/warm instances.

**Acceptance criteria:** connection count remains bounded under expected parallel Vercel instances; transaction/session semantics used by RLS and `SET LOCAL` remain correct; load test proves no connection-exhaustion failure.

---

## PG-AUD-REL-004 — In-flight database disconnects are not treated as potentially indeterminate writes

**Priority:** P2  
**Type:** write-recovery correctness

**Problem:** a real Vercel log during audit showed `SSL connection has been closed unexpectedly` on a read. `pool_pre_ping` handles stale connections before a query but cannot prevent an in-flight disconnect. The browser's repair recovery wrapper handles timeouts/network failures as ambiguous, but a server `500` is not automatically treated as “commit may have happened.” If PostgreSQL commits and the connection dies before acknowledgement, a later user retry with a new idempotency key could duplicate intent.

**Proposed solution:** classify database disconnect/commit-ack-loss errors distinctly. For mutation endpoints, return/translate them into an uncertain-write condition that drives the existing authoritative idempotency recovery flow rather than a generic failed write. Ensure recovery checks use the original idempotency key.

**Acceptance criteria:** tests simulate post-commit connection loss; client/server recover the committed result or surface explicit uncertainty without replaying with a new key.

---

## PG-AUD-REL-005 — External provider timeout exceeds the API deadline

**Priority:** P3  
**Type:** timeout hierarchy

**Problem:** `NhtsaRecallCollector` defaults to a 10-second network timeout while the PartGraph API deadline is about 8 seconds. The blocking `urlopen` call runs inside `asyncio.to_thread`, so cancellation of the request coroutine does not guarantee the worker thread/socket stops immediately.

**Proposed solution:** make provider connect/read timeout materially shorter than the business/API deadline, and keep the browser deadline longer than the API deadline. Prefer cancellation-friendly async HTTP for future connectors if practical.

**Acceptance criteria:** provider timeout < API deadline < browser deadline; timed-out provider work does not continue consuming significant worker capacity after the API has abandoned the request.

---

## PG-AUD-REL-006 — Provider ingestion is synchronous and has no durable backpressure mechanism

**Priority:** P3 / future scale  
**Type:** ingestion scaling

**Problem:** current operator ingestion is request → external fetch → validate → stage → commit → response. This is acceptable for narrow operator-triggered MVP ingestion but does not scale to continuous/high-volume providers because there is no durable job queue, bounded worker pool, retry scheduler or dead-letter state.

**Proposed solution:** do not add queue complexity prematurely. When ingestion volume requires it, introduce a durable job record/queue with bounded workers, exponential backoff, provider rate limits, idempotent batch keys, terminal failure state and operator observability.

**Acceptance criteria:** current simple path remains until justified; high-volume rollout cannot be enabled without a documented queue/backpressure design.

---

## PG-AUD-REL-007 — Operational observability is debugging-grade, not production-grade

**Priority:** P2  
**Type:** monitoring / SLOs

**Problem:** request IDs, logs, latency logging, readiness checks, Vercel logs and Neon diagnostics exist, but there is no unified metrics/tracing/error-monitoring layer and no explicit alerting for error rate, latency, database connectivity, provider failure, photo finalization or backup protection.

**Proposed solution:** add a lightweight OpenTelemetry-compatible instrumentation layer and production error/metrics backend appropriate to the project scale. Define a small initial SLO set (availability, p95 API latency, mutation-error rate, DB readiness, provider ingestion failures, media reconciliation failures) and actionable alerts.

**Acceptance criteria:** production operators can answer “what broke, where and since when?” without manual log archaeology; every alert has a runbook/owner.

---

## PG-AUD-REL-008 — Service-worker cache lifecycle can accumulate obsolete hashed assets

**Priority:** P3  
**Type:** offline cache hygiene

**Problem:** `web/public/sw.js` uses a fixed `partgraph-shell-v1` cache name and caches same-origin shell assets. New hashed assets are harmlessly fetched when names change, but obsolete hashed assets inside the same cache are not pruned until the cache namespace itself changes.

**Proposed solution:** version the shell cache as part of releases or maintain an explicit current-asset manifest and delete stale entries during activation/update. Preserve the rule that `/api/` is never cached.

**Acceptance criteria:** repeated releases do not grow the shell cache indefinitely; offline navigation still works; API/private response caching remains prohibited.

---

## PG-AUD-REL-009 — Concurrent offline-pack refreshes can rewrite the last confirmed snapshot during offline transition

**Priority:** P2  
**Type:** offline continuity / async race  
**Execution status:** COMPLETE

**Problem:** the Phase 9 offline/degraded acceptance run on `57d7da853a8a957e04100de1dc53cd3eb6de70e5` failed with `offline reload invented a newer sync timestamp` in MVP Final Validation CI #243. `OfflineContinuity` could schedule overlapping `sync()` calls from lifecycle events and its interval, while `refreshOfflineRepairPack()` wrote to `sessionStorage` before the caller could reject a stale response. A later response could therefore replace the last confirmed pack while the browser was transitioning offline. Multiple offline-pack GETs are legitimate across initial load, active-session changes, degraded recovery, and reconnect; request count itself is not the invariant. The defect was stale refresh authority over the cached snapshot.

**Proposed solution:** make offline-pack synchronization generation-aware and burst-coalesced. A newly scheduled sync must supersede older in-flight work, invalidate older cache-write eligibility without deleting the last confirmed pack, and only publish a fresh result when it is still the current generation and the client is online. Preserve the existing reconnect refresh and logout cache-clearing behavior.

**Acceptance criteria:** burst lifecycle events do not create overlapping authoritative refreshes; a stale in-flight response cannot overwrite the cached pack or UI after a newer sync/offline transition; offline reload preserves `pack_version`, `server_sequence`, and `generated_at`; reconnect performs a fresh authoritative refresh; Phase 9 offline/degraded acceptance and the exact-head final matrix pass.

**Remediation update — COMPLETE on `partgraph-mvp-consolidation`.**  
Exact remediation proof head: `41ff18613a3c879a52e77b9a8454d04827a392eb`.

Remediation performed:

- added generation-aware sync scheduling in `OfflineContinuity.tsx`; a newer lifecycle request supersedes older work
- coalesced burst event scheduling through one replaceable timer instead of launching an independent delayed sync for every event
- added `invalidateOfflineRepairRefreshes()` in `offline-repair.ts`; a superseded refresh can still finish its network request but loses authority to overwrite `sessionStorage`
- publish of a fresh pack now also requires the sync generation to remain current and the browser to still be online
- cleanup invalidates outstanding refresh authority without deleting the last confirmed pack; logout still clears the private pack through the existing auth-clear path

Proof on the exact remediation head:

- the previously failing Phase 9 offline/degraded Chromium acceptance passed, including preserved `pack_version`, `server_sequence`, and `generated_at` across offline reload plus a fresh reconnect update
- MVP Final Validation CI #247: all 18 jobs passed
- Web CI/CD #972, API CI/CD #1109, Extraction Pipeline CI #448, Canonical Publication CI #385, Reference Repair Runtime CI #400, Database Reliability CI #235, Operational Observability CI #194, and Web Dependency Advisory Scan #236: passed
- Vercel Preview `dpl_GRRZDdM1A8ZJS5UdcVvoPTd66X1p`: READY, Preview target only
- no Production configuration, database schema, automotive data, PR merge, or Phase 10 action was performed

---


# D. Deployment, release and repository governance

## PG-AUD-DEP-001 — PR #84 must not be merged before an explicit production cutover sequence

**Priority:** P0 release blocker  
**Type:** production compatibility

**Problem:** the consolidation implementation is hundreds of commits ahead of `main`, the preview schema is 0059, and production is deliberately still 0020. Merging the application code without a controlled schema/environment promotion can create application/schema incompatibility. The blueprint also requires every schema transition to be tested on a production copy first.

**Proposed solution:** create a cutover runbook before merging PR #84. It must include: production-copy migration rehearsal; backup/restore checkpoint; exact schema path 0020→0059; environment secrets/keys/storage verification; application compatibility window; canonical-data publication decision; smoke tests; rollback criteria; and traffic/domain promotion. Do not collapse these into one uncontrolled deploy.

**Acceptance criteria:** production-copy rehearsal passes; rollback is possible; code and database compatibility is proven; explicit authorization is obtained before migration/merge.

---

## PG-AUD-DEP-002 — Vercel build automatically runs Alembic upgrades

**Priority:** P2  
**Type:** deployment coupling

**Problem:** `api/pyproject.toml` runs `alembic upgrade head` during Vercel production builds and consolidation-preview builds. Production has not accidentally drifted—it remained at 0020 during audit—but this configuration makes schema mutation a side effect of application build/deploy.

**Proposed solution:** remove production schema promotion from generic application build. Run migration as a separately authorized/preflighted release step against the intended branch/database, verify it, then deploy compatible application code. Preview migration can also be made explicit if reproducibility benefits outweigh convenience.

**Acceptance criteria:** a documentation/app build cannot mutate production schema merely because an environment variable points at production; migration has an explicit promotion/rollback gate.

---

## PG-AUD-DEP-003 — `main` and consolidation branches are unprotected

**Priority:** P1  
**Type:** repository governance

**Problem:** GitHub reported both `main` and `partgraph-mvp-consolidation` as `protected=false`, with no required status checks. CI is strong, but GitHub does not enforce those checks before a direct code update.

**Proposed solution:** add branch rules/rulesets appropriate to the project's workflow. Require relevant CI for code changes, block force pushes/deletions, and preserve a narrowly controlled path for the deliberate direct-to-main roadmap/bookkeeping workflow if that workflow must remain. Avoid a rule configuration that makes `docs/ROADMAP_LIVE.md` bookkeeping impossible.

**Acceptance criteria:** code cannot bypass required checks accidentally; protected history cannot be force-deleted; intentional documentation bookkeeping remains workable by explicit policy.

---

## PG-AUD-DEP-004 — PR #84 description is stale and contradicts current roadmap state

**Priority:** P2  
**Type:** cutover/documentation drift

**Problem:** PR #84 still references older proof commits/run numbers, an older preview schema (`0058_downstream_materializer`), and a “Still in progress” list containing Phase 7 work that is now complete. The live roadmap correctly marks Phase 7 complete and the branch is at 0059.

Because PR #84 is the primary eventual cutover artifact, stale status text can cause an implementer/reviewer to re-do completed work or miss the real remaining gates.

**Proposed solution:** update the PR body after this audit to point at `0a6918...` as bookkeeping-synchronized head, `7b1d7df...` as the final implementation/data proof, the correct green workflow runs, schema 0059, Phase 7 completion, and only real remaining cutover/Phase 1/Phase 6/Phase 9 gates. Do not merge the PR as part of that documentation update.

**Acceptance criteria:** PR description and `ROADMAP_LIVE.md` agree on completed/pending work and cutover blockers.

---

## PG-AUD-DEP-005 — Documentation-only `main` commits trigger Production deployments

**Priority:** P2  
**Type:** deployment trigger scope / production governance  
**Execution status:** BLOCKED

**Problem:** the Phase 9 closeout update to `docs/ROADMAP_LIVE.md` on `main` changed no `api/`, `web/`, migration, or application file, yet the Vercel Git integration automatically started and completed Production deployment `dpl_CgyKourTBDycuEaBFiTu6UFqwaqR`. The deployment was application-content-equivalent because only documentation changed, but the production deployment trigger is broader than the intended release boundary and makes routine roadmap bookkeeping create unnecessary Production builds.

**Proposed solution:** during the authorized deployment-governance/Phase 10 work, configure a path-aware Vercel ignore/build rule or equivalent project setting that skips Production builds when a commit changes only non-runtime documentation. The rule must still deploy when either the API project root or the sibling `web/` bundle changes, and it must not weaken explicit release deployment controls.

**Acceptance criteria:** documentation-only `main` commits do not create Production deployments; runtime-affecting `api/` or `web/` changes still do; the rule is tested with both skip and deploy cases; no Production configuration change is made without explicit authorization.

---

# E. Frontend accessibility, reflow and browser behavior

Engineering accessibility target for future sign-off: **WCAG 2.2 Level AA**. At audit time, public-sector procurement/use may have additional legal obligations (for example ADA Title II currently references WCAG 2.1 AA and Section 508 uses the Revised 508/WCAG 2.0 A/AA framework). Legal applicability depends on deployment/customer context; this register is an engineering remediation plan, not legal advice.

## PG-AUD-UI-001 — Repair Log and one Garage field lack proper programmatic labels

**Priority:** P1  
**Type:** accessibility / forms

**Problem:** several `RepairLog.tsx` form controls rely on placeholders or nearby headings rather than an associated `<label>`/accessible name: repair selector, storage-location inputs, fastener kind/label/origin fields, observation category/text, photo purpose and file input. The Garage model-year input also has adjacent visible label text that is not programmatically associated.

**Proposed solution:** give every input/select/textarea/file input a persistent visible `<label>` with `htmlFor`/`id` or an equivalent wrapping label. Use `aria-describedby` for instructions/errors. Do not use placeholder as the only label.

**Acceptance criteria:** browser accessibility tree exposes a useful name for every control; axe/manual screen-reader review reports no unlabeled form controls.

---

## PG-AUD-UI-002 — Mobile sticky headers use hard-coded offsets that can overlap at enlarged text

**Priority:** P1/P2  
**Type:** responsive reflow / focus visibility

**Problem:** below 720px the authenticated account strip becomes a column and can become taller than 46px, while the workspace nav still assumes `top:46px` and repair nav roughly `top:96/98px`. PartGraph's own 150–200% text option and browser zoom can enlarge those layers further, allowing sticky regions to overlap content/focused controls.

**Proposed solution:** derive stacked sticky offsets from layout rather than duplicated magic numbers. Options include CSS custom properties set by the actual header, a single sticky stack container, or eliminating unnecessary independent sticky layers on narrow viewports.

**Acceptance criteria:** at 320 CSS px, 200% browser zoom, PartGraph 200% text, and combined stress cases, no focused/interactive element is obscured and no two-dimensional page scroll is required for ordinary text content.

---

## PG-AUD-UI-003 — Dynamic workflow messages are not consistently announced to assistive technology

**Priority:** P1/P2  
**Type:** status-message accessibility

**Problem:** availability and some inventory messages use `role=status`/`aria-live`, but many Garage, Repair Log, Readiness, Start Repair and Completion success/error states are plain dynamically inserted `<div>` elements. Screen-reader users may not know that an action succeeded/failed if focus stays on the triggering control.

**Proposed solution:** introduce shared `StatusMessage` and `ErrorAlert` components with consistent `role`, `aria-live`, atomic behavior and visual styles. Use assertive alerts only for urgent errors; normal saves/updates should be polite status messages.

**Acceptance criteria:** screen-reader testing confirms saves, failures, lease changes and other asynchronous workflow outcomes are announced once without stealing focus unnecessarily.

---

## PG-AUD-UI-004 — Garage declares a tablist without implementing the tab pattern

**Priority:** P2  
**Type:** ARIA semantics

**Problem:** the manual/VIN mode switch uses `role="tablist"`, but child controls are ordinary buttons without `role=tab`, `aria-selected`, `aria-controls`, associated tabpanels or arrow-key behavior. This advertises a composite widget contract that is not implemented.

**Proposed solution:** either implement the full WAI-ARIA tab pattern (including roving focus and arrow navigation) or remove tab semantics and expose the two choices as normal toggle buttons. Prefer the simpler semantic model unless real tab semantics materially improve usability.

**Acceptance criteria:** accessibility tree/keyboard behavior match the semantics actually declared.

---

## PG-AUD-UI-005 — Settings declares radio groups without native/radio keyboard behavior

**Priority:** P2  
**Type:** ARIA composite widget

**Problem:** Units and Text Size use buttons with `role=radio` inside `role=radiogroup`, but all choices remain independent tab stops and arrow-key/radio-group behavior is not implemented.

**Proposed solution:** prefer native `<input type="radio">` controls styled as cards, or implement the complete radio-group keyboard pattern with roving tabindex/arrow selection.

**Acceptance criteria:** one predictable Tab stop enters each group; arrow keys change radio selection according to the chosen pattern; `aria-checked`/native checked state stays synchronized.

---

## PG-AUD-UI-006 — Single-page navigation does not manage focus/orientation

**Priority:** P2  
**Type:** keyboard/screen-reader navigation

**Problem:** `PartGraphShell.navigate()` changes React state/hash and scrolls to the top but does not move focus to the new main heading/content, update document title per view, or provide a skip-to-main link. Keyboard/screen-reader users can remain focused in the old navigation context while the whole workspace changes silently.

**Proposed solution:** add a main-content focus target, skip link, route-change focus policy and route-specific document title. Prefer instant/no animation for focus-driven navigation when reduced motion is requested.

**Acceptance criteria:** after activating navigation, assistive technology receives clear new-page context; keyboard users can skip repeated navigation.

---

## PG-AUD-UI-007 — Repair-photo alt text describes purpose, not meaningful content

**Priority:** P2  
**Type:** non-text content accessibility

**Problem:** repair images receive generated alt text such as “damage repair” or “current step repair.” That identifies category but not what the image shows (crack location, connector orientation, part number, routing, before/after condition). For repair memory, the visual information can be functional evidence.

**Proposed solution:** add an optional user-authored image description/caption and associate photos with observations where possible. Use purpose-only text only when the image is truly decorative/redundant. Do not auto-invent descriptions as canonical truth.

**Acceptance criteria:** meaningful repair evidence can have equivalent accessible description; existing photo records remain valid when no description exists.

---

## PG-AUD-UI-008 — No automated accessibility/cross-browser regression gate exists

**Priority:** P2  
**Type:** test coverage

**Problem:** Web CI typechecks/builds/scans dependencies and smoke-tests the container/security headers, but `web/package.json` has no browser test script and the repo has no current browser E2E suite. There is no axe-style scan, keyboard regression, viewport matrix, zoom/reflow check or explicit Firefox/Safari/iOS validation.

**Proposed solution:** add Playwright (or equivalent) with a small supported-browser/viewport matrix and axe checks on core owner flows. Add manual release checks for keyboard and at least one real screen reader because automation cannot prove full accessibility.

**Acceptance criteria:** core Garage→Start Repair→Readiness→Guidance→Log flows run in the supported browser matrix; automated accessibility checks gate regressions; manual checklist is documented.

---

## PG-AUD-UI-009 — Browser-support policy is implicit in the Vite version

**Priority:** P2/P3  
**Type:** compatibility policy

**Problem:** no explicit PartGraph browser matrix is declared; build target therefore follows Vite defaults. That is reasonable technically but makes the product support boundary accidental and changeable when tooling upgrades.

**Proposed solution:** document the minimum supported desktop/mobile browsers/versions based on real user/device goals, set build/test configuration accordingly, and keep optional SpeechRecognition outside the minimum contract.

**Acceptance criteria:** support matrix is explicit; CI tests representative browsers; unsupported optional APIs degrade gracefully.

---

## PG-AUD-UI-010 — Localized contrast and target-size cleanup remains

**Priority:** P3  
**Type:** visual accessibility

**Problem:** most current repair UI has strong contrast, but some muted/placeholder text is borderline. Example: repair placeholder `#657a83` on `#0f1a20` is about 3.9:1 by WCAG relative luminance, below 4.5:1 for ordinary text. Some small Home muted strings also need measurement. A few controls such as the 36px inventory mic are smaller than the app's general 44–48px control convention.

**Proposed solution:** run an automated+manual contrast inventory, move weak text tokens to compliant values, and standardize touch/click target sizing where practical without unnecessarily enlarging compact controls.

**Acceptance criteria:** normal text meets target contrast; interactive states remain visually distinct; primary touch controls have a documented sizing rule.

---

## PG-AUD-UI-011 — Custom YearWheel needs either real AT proof or retirement

**Priority:** P3  
**Type:** custom control / dead-code candidate

**Problem:** `YearWheel.tsx` has thoughtful pointer/wheel/keyboard handling and `role=spinbutton`, but the current Garage implementation uses a normal numeric year input and does not import YearWheel. The component itself contains a focusable spinbutton with focusable year buttons, an unusual accessibility pattern.

**Proposed solution:** first run an import/dependency graph. If YearWheel is unused, remove it and its obsolete `.year-wheel*` CSS. If it is intentionally retained for a future route, test with NVDA/VoiceOver and simplify its focus model before use.

**Acceptance criteria:** no unused custom widget remains without a reason; any active custom spinbutton passes keyboard/screen-reader tests.

---

# F. Codebase maintainability and dead/legacy paths

## Phase 8–9 Category F remediation update — 2026-09-19

**`PG-AUD-CODE-002`: CURRENT CONTROL COMPLETE / FUTURE BACKLOG.**  
Exact current-control proof head: `41ff18613a3c879a52e77b9a8454d04827a392eb`.

Current-control remediation performed:

- audited the legacy vehicle-selector class family against every current TSX surface; exact class-token usage was zero for `vehicle-selector`, `year-field`, `selector-fields`, `vin-form`, `field-label-row`, `field-note`, the retired `combo*` family, `selector-action`, `result-card*`, and `vin-input`
- removed 228 lines of proven-unused selector/combobox/VIN/result-card CSS from `web/src/app.css`
- removed the two remaining dead patch-layer references (`.field-label-row` and `.combo__option`) from `web/src/accessibility-ui.css`
- extended `web/scripts/validate-retired-frontend-assets.mjs` to scan all active TS/TSX/CSS/HTML source and fail if any exact retired class token returns
- deliberately did **not** perform a broad token/theme/cascade rewrite; active stylesheet ownership and the later visual/multi-browser hardening remain tied to `PG-AUD-UI-008`/`PG-AUD-UI-009`

Proof on the exact current-control head:

- Web CI/CD #972 passed the strengthened retired-asset guard, TypeScript typecheck, production web build, container build, and running-container smoke
- Phase 9 real Chromium browser E2E passed on the same head
- MVP Final Validation CI #247 passed all 18 jobs after the independently discovered `PG-AUD-REL-009` offline race was remediated
- all eight other exact-head regression workflows passed; Vercel Preview `dpl_GRRZDdM1A8ZJS5UdcVvoPTd66X1p` is READY
- remaining CODE-002 scope is architectural stylesheet/token consolidation plus broader visual/multi-browser proof, so the finding is not falsely marked `COMPLETE`


**`PG-AUD-CODE-001`: COMPLETE on `partgraph-mvp-consolidation`.**  
Exact remediation proof head: `a1c868b39bc2ff6044093a172a761a2d5883df68`.

Remediation performed:

- removed the compatibility-only `api/partgraph/auth/`, `api/partgraph/user_vehicle/`, `api/partgraph/repair_definition/`, and `api/partgraph/repair_experience/repair_session/` namespaces after import-use proof
- migrated remaining repair-experience consumers to canonical `partgraph.identity.*`, `partgraph.knowledge.*`, and direct `partgraph.repair_experience.*` modules
- retained the current `repair_experience.auth` internal dependency seam; it is not the retired top-level `partgraph.auth` package
- removed stale Reference Repair Runtime workflow paths that still linted the retired repair-definition directory
- added `api/tests/test_retired_compatibility_bridges.py`, which resolves absolute and relative imports with Python AST and fails if a retired package or import path returns
- wired the canonical-import guard into permanent API CI

Proof on the exact remediation head:

- API CI/CD #1103: passed, including canonical-import guard, migrations/baseline/RBAC checks, API container build, and running-container smoke
- Reference Repair Runtime CI #394: passed the reference-fleet runtime gate
- MVP Final Validation CI #235: passed all 18 Phase 9 jobs
- Extraction Pipeline CI #442, Canonical Publication CI #379, Database Reliability CI #229, Operational Observability CI #188, Web CI/CD #966, and Web Dependency Advisory Scan #230: passed
- Vercel Preview `dpl_cNHbTJs8zmq53EM9ijRypK8wMJSw`: READY, Preview target only
- no API schema migration was added, no automotive data changed, no Production configuration changed, PR #84 remains unmerged, and Phase 10 was not started

The original `PG-AUD-CODE-001` finding below is retained as the audit baseline.

**`PG-AUD-CODE-004`: COMPLETE on `partgraph-mvp-consolidation`.**  
Exact remediation proof head: `3bc78cf918cd9957beab0597b30c17da6f7b841f`.

Remediation performed:

- removed the permanently hidden `.memory-session-bar` subtree from `web/src/RepairMemory.tsx`
- removed the dead Readiness-only session selector and hidden lease-acquire/takeover handlers
- removed the corresponding stale `.memory-session-bar` / `.memory-session-state` CSS and obsolete comment
- preserved active-session resolution through `active-repair.ts`; visible lease/edit authority remains available in Overview and Guided Repair
- extended `web/scripts/validate-retired-frontend-assets.mjs` so the retired hidden markup, styles, and handlers cannot return silently

Proof on the exact remediation head:

- Web CI/CD #956: passed, including the retired-asset guard, TypeScript typecheck, production web build, container build, and HTTP/security-header smoke
- MVP Final Validation CI #215: passed all 18 Phase 9 jobs, including real Chromium browser E2E
- Vercel Preview `dpl_8M4y21QZAP5xJoQSjxquAQazQpdP`: READY, Preview target only
- no API schema, database migration, automotive data, Production configuration, PR merge, or Phase 10 action was performed

The original finding statement below is retained as the audit baseline.


## PG-AUD-CODE-001 — Compatibility bridge packages need an explicit retirement decision

**Priority:** P3  
**Type:** architecture cleanup

**Problem:** legacy import namespaces such as `partgraph.auth`, `partgraph.user_vehicle`, `partgraph.repair_definition` and `partgraph.repair_experience.repair_session` mostly re-export canonical implementations. They are not duplicate business logic today, but they keep two apparent module layouts alive and can confuse future code search/refactoring.

**Proposed solution:** generate an import-use graph. Migrate remaining imports to canonical namespaces, add a temporary deprecation note if external/internal callers still rely on bridges, then remove only when usage reaches zero.

**Acceptance criteria:** one canonical module path per capability; no import breakage; no bridge removed based only on filename similarity.

---

## PG-AUD-CODE-002 — Frontend has patch-layer/legacy CSS that increases cascade fragility

**Priority:** P3  
**Type:** frontend maintainability

**Problem:** current styling is distributed across broad `app.css`, workspace CSS files, `light-panel-contrast.css`, `accessibility-ui.css` and older selectors. Comments explicitly describe one layer as superseding older themes. `app.css` still contains old vehicle-selector/year-wheel/combo/VIN styles while current Garage uses newer `garage-workspace.css`. This cascading override structure makes reflow/contrast behavior harder to reason about and contributed to “magic number” layout assumptions.

**Proposed solution:** inventory selectors against rendered components, establish shared design tokens, move active workspace rules to their owning stylesheet/component, and delete proven-unused legacy selectors after browser visual regression tests.

**Acceptance criteria:** no active selector depends on accidental import order; redundant legacy blocks are removed only with usage proof; visual/a11y snapshots remain stable.

---

## PG-AUD-CODE-003 — Candidate unused frontend assets should be proven before deletion

**Priority:** P3  
**Type:** dead-code cleanup

**Problem:** `web/src/production-launch.css` appears in the branch tree but is not imported by `main.tsx`; `YearWheel.tsx` is not imported by current `GarageWorkspace.tsx`; additional legacy selectors remain in `app.css`. These are strong cleanup candidates, not yet safe-to-delete facts because a full import graph was not executed during the connector-only audit.

**Proposed solution:** run TypeScript/CSS import graph and grep/AST selector usage on a local checkout. Remove only assets with zero imports/runtime references and verify the production bundle/browser flows afterward.

**Acceptance criteria:** dead files/selectors removed with evidence; no feature is removed merely because its filename looks old.

---

## PG-AUD-CODE-004 — Hidden legacy Readiness session bar has stale intent/comment

**Priority:** P3  
**Type:** hidden UI/code debt

**Problem:** `repair-memory.css` sets `.memory-session-bar { display: none; }` while `RepairMemory.tsx` still renders and maintains the session selector/lease controls. The stylesheet comment says the block is hidden “until Inventory is replaced by the equipment catalog UI,” but the equipment catalog UI now exists. Either the selector is intentionally redundant with the current repair shell, or the old condition is stale.

**Proposed solution:** decide the intended UX. If the current-repair shell owns selection, delete the hidden bar/state paths and update comments. If Readiness still needs direct session switching, restore it accessibly and reconcile with shell navigation.

**Acceptance criteria:** no permanently hidden interactive subtree with stale rationale; one clear owner for current-repair selection.

---

# G. Incomplete roadmap work that still exists through the Phase 7 boundary

These items are deliberately **not** called Phase 7 implementation failures. They are older/concurrent roadmap gates that remain incomplete even though Phase 7's deep reference-vehicle exit gate passed.

## PG-AUD-ROAD-001 — Phase 1 hosted durable-photo persistence proof remains incomplete

**Priority:** P1 before production media  
**Type:** roadmap incomplete / durable storage

**Problem:** Phase 7 proves observation/photo runtime behavior (create, attach, retrieve/hash, delete) but does not prove hosted durable private object persistence across redeploy/restart. The roadmap explicitly leaves the Phase 1/Phase 9 hosted durable-photo requirement pending.

**Proposed solution:** configure/verify the intended private durable object store in the hosted environment, upload evidence, redeploy/restart, prove authorized retrieval remains valid, prove unauthorized retrieval is denied, and exercise deletion/reconciliation.

**Acceptance criteria:** media survives application redeploy/cold start independently of ephemeral filesystem state; owner isolation and lifecycle tests pass.

---

## PG-AUD-ROAD-002 — Phase 6 deployed NHTSA HTTP ingestion proof remains incomplete

**Priority:** P2  
**Type:** roadmap incomplete / provider pipeline

**Problem:** the deterministic collector, staging policy, approved binding and safety tests are complete. The roadmap still requires one real deployed operator-endpoint HTTP invocation. Existing pending NHTSA candidates do not by themselves prove that exact deployed invocation path.

**Proposed solution:** invoke the deployed operator NHTSA staging endpoint using the approved enabled binding, capture request/audit/ingestion-batch provenance, verify candidates remain pending/non-exact and that zero verified evidence/MechanicalClaims/canonical facts are auto-created.

**Acceptance criteria:** live deployed request is traceable end to end through operator audit + ingestion batch + staged candidates; governance still fails closed.

---

## PG-AUD-ROAD-003 — Phase 6 broad canonical repair knowledge remains incomplete

**Priority:** P2 / roadmap  
**Type:** roadmap incomplete / data population

**Problem:** the generic pipeline is implemented and Phase 7 proves deep behavior for the first exact vehicle/repair set, but Phase 6 remains “in progress” because canonical repair knowledge is still a small reviewed reference set rather than broad coverage.

**Proposed solution:** continue using the same evidence/authority/review/materializer path to ingest reviewed knowledge. Do not solve breadth by weakening applicability, majority-vote conflict logic, or embedding facts in code. Phase 8 reference-fleet population should remain data-only.

**Acceptance criteria:** coverage grows through verified data without make/model-specific application code and without altering the evidence/publication invariants.

---

# H. Release/testing gates that are planned later but must not be forgotten

These are important audit findings, but many are naturally Phase 9/release work rather than reasons to retroactively mark Phase 7 incomplete.

## PG-AUD-TEST-001 — Blueprint testing contract is broader than current permanent CI

**Priority:** P2 before final release  
**Type:** validation coverage

**Problem:** `docs/BLUEPRINT.md` calls for browser E2E, randomized acceptance, five-model acceptance, offline/degraded tests, timeout/reconciliation tests, production-copy migration and data-free-source-code checks in addition to unit/API/security/RLS/migration/RBAC layers. Current permanent workflows are API, Web, Extraction, Publication and Reference Runtime. Many backend checks are strong, but browser/accessibility and final release campaigns are not yet permanent gates.

**Proposed solution:** implement the missing layers in the roadmap phase intended for final validation. Reuse the current reference-runtime/fresh-DB pattern; avoid creating vehicle-specific CI branches.

**Acceptance criteria:** before production cutover the blueprint's required test-layer checklist is explicitly mapped to a workflow/test command or documented manual release check, with no silent omissions.

---

# I. Database and infrastructure cleanup register

## Post-audit Category A cleanup status

The audit-baseline estimates below are retained for historical traceability, but the corresponding Category A database cleanup has been completed on the consolidation preview through forward migrations 0060 and 0061.

Current consolidation preview verification at `0061_retire_legacy_specs`:

- workbook-derived unverified vehicle configurations: **0**
- workbook staging rows (`curated_workbook_import`): **0**
- unverified coverage rows: **0**
- legacy verified `vehicle_specification_candidate` staging rows: **0**

No production cleanup/migration was performed. Production remains at `0020_catalog_coverage` pending an explicitly authorized cutover.

## Strong database cleanup candidate — audit baseline, now completed in consolidation preview

Selected Asian workbook lineage:

- 363 pending staging identity rows
- 363 unverified vehicle configurations
- 363 unverified coverage rows
- 2 associated batch rows
- total **1,091 rows**
- approximately **695 KiB logical row payload**
- no user-vehicle, repair-definition, MechanicalClaim or fitment dependencies found during audit

## Conditional database cleanup candidate — audit baseline, now completed in consolidation preview

Legacy specification staging:

- 5 rows marked verified under the pre-modern staging model
- no corresponding modern `catalog_verified_evidence`
- approximately **9.7 KiB logical row payload**
- migrate any still-needed facts into modern evidence first

## Combined audit-baseline cleanup

- **1,096 rows**
- approximately **705 KiB logical row payload**

Do **not** run `VACUUM FULL` merely to reclaim this amount. PostgreSQL can reuse deleted space; physical database size includes pages/indexes/metadata and will not shrink proportionally after ordinary deletion.

## Keep

Do not delete merely because they are unpromoted or duplicated by canonical state:

- 20 pending NHTSA safety/mechanical candidates observed in staging
- 282 current promoted/raw provenance rows that support the evidence → claim audit chain
- equipment catalog rows; operational catalog authority is now the versioned dataset
- historical migrations 0001–0061, including the legacy data migrations and forward cleanup migrations
- `api/data/Selected_Asian_Brands_1996_2000.xlsx`, because immutable migrations 0017/0020 require the API path for historical reconstruction even though its live database lineage is retired

## Neon preview-branch cleanup candidates

Two older preview branches were identified as likely retirement candidates during audit:

- `preview/partgraph-reference-fleet-mvp` (~34.1 MiB apparent logical size)
- `preview/partgraph-raw-catalog-collectors` (~33.6 MiB apparent logical size)

Combined apparent logical branch size: ~67.7 MiB. Neon copy-on-write means deleting them does not guarantee equal physical storage reclamation. **Do not delete without explicit authorization and a final dependency/diagnostic-value check.**

---

# J. Recommended remediation order

This order is based on blast radius and production risk, not on the five audit passes. Completed Category A items are retained in the ordering for historical context but should not be re-opened without new evidence.

1. **Correct schema metadata drift** (`PG-AUD-DATA-001`) — completed on consolidation branch.
2. **Close production safety blockers**: database DR, photo DB/blob consistency design, hosted CSP, controlled preview bootstrap, branch protection.
3. **Decouple production migrations from Vercel builds** and write the PR #84 cutover runbook before any merge.
4. **Harden indeterminate database-write recovery and serverless connection pooling**.
5. **Fix P1/P2 accessibility defects**: labels, sticky reflow, live announcements, focus management, incorrect tab/radio semantics.
6. **Add deployed/browser regression gates** including hosted security headers and accessibility/browser E2E.
7. **Finish older roadmap gates**: hosted durable-photo proof and deployed NHTSA HTTP proof; continue Phase 6 knowledge breadth through data only.
8. **Move generic equipment catalog data out of Python** — operational path completed through the versioned dataset; any remaining unused generator modules are a later code-cleanup concern.
9. **Run forward legacy-data cleanup** — completed on consolidation preview through 0060/0061; production execution remains part of authorized cutover.
10. **Remove proven dead/duplicate repo assets and compatibility bridges** — Category A duplicate/archive data cleanup, the retired frontend assets, hidden Readiness controls, and the audited compatibility bridge packages are complete; remaining Category F work is the separately tagged CSS-maintainability backlog.

## Definition of audit completion

The register is re-audited through Phase 9 when the Phase 8–9 status reassessment and any newly observed findings are recorded here with an execution status. Audit completion does **not** mean PR #84 is approved for merge, production is ready for migration, blocked/backlog items are complete, or Phase 10 has started. Remediation continues one `ELIGIBLE` item at a time on `partgraph-mvp-consolidation`; production cutover remains separately gated and unauthorized.