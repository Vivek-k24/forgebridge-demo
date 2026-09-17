# PartGraph Phase 0–7 Remediation Execution Gate

Status: **Authoritative execution-status overlay for `docs/PHASE_0_7_AUDIT_REMEDIATION_REPORT.md` while the roadmap is only complete through the Phase 7 boundary.**

This file does not change the audit findings, architecture, roadmap order, or acceptance criteria. It prevents remediation work from pulling Phase 8, Phase 9, Phase 10, future-provider, final-release, or still-unresolved cross-task work forward prematurely.

## Mandatory execution rule

Before starting any audit remediation item, check the whole repository/roadmap for prerequisites and downstream dependencies.

- `COMPLETE` — already implemented/proven at the currently available phase boundary. Do not reopen without new evidence.
- `ELIGIBLE` — can be remediated now without depending on an unfinished or untouched roadmap/remediation task.
- `BLOCKED` — do not implement/close it now. A named prerequisite, owner decision, infrastructure capability, or later phase must happen first.
- `BACKLOG` — intentionally defer it because its natural execution point is a later roadmap phase or after another category stabilizes.
- `CURRENT CONTROL COMPLETE / FUTURE BACKLOG` — the present-phase safety control is complete, but future-scale/future-adapter acceptance must be revalidated when that future capability is actually introduced.

A higher audit priority does **not** override `BLOCKED` or `BACKLOG`.

The current roadmap boundary is:

- Phase 7 deep primary-vehicle proof: complete.
- Phase 8 five-model reference fleet: not started.
- Phase 9 final MVP validation campaign: not started.
- Phase 10 production MVP cutover: not started and requires explicit production approval.
- Phase 1 hosted durable-photo persistence proof: still pending and explicitly tied to later hosted/final validation work.
- Phase 6 deployed NHTSA HTTP proof and broad canonical repair-knowledge population: still pending.

If an item depends on any of those unfinished tasks, or on another unfinished remediation item, it remains blocked/backlog rather than being implemented speculatively.

---

# A. Data model, schema and canonical-data integrity

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-DATA-001` | COMPLETE | Current schema/ORM/source-policy alignment was independently remediable. |
| `PG-AUD-DATA-002` | COMPLETE | Operational catalog was externalized without waiting for later vehicle population. |
| `PG-AUD-DATA-003` | COMPLETE | Publication policy/runbook was definable without performing production publication/cutover. |
| `PG-AUD-DATA-004` | COMPLETE | Legacy preview provenance cleanup was independently remediable. |
| `PG-AUD-DATA-005` | COMPLETE | Orphaned preview workbook lineage cleanup was dependency-proven and forward-only. |
| `PG-AUD-DATA-006` | COMPLETE | Duplicate/archive assets were removed only after dependency proof. |

---

# B. Security and trust boundaries

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-SEC-001` | COMPLETE | Hosted CSP is a current deployment-path control and does not require Phase 8–10. |
| `PG-AUD-SEC-002` | COMPLETE | Preview bootstrap authority can be secured independently of future phases. |
| `PG-AUD-SEC-003` | COMPLETE | Operator DB least privilege is a current trust-boundary control. |
| `PG-AUD-SEC-004` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Existing generic outbound-network protection remains sufficient for the current fixed NHTSA path. Revalidate only when a stored provider URL becomes executable by a future adapter. |
| `PG-AUD-SEC-005` | COMPLETE | Photo decode/file hardening is a current upload boundary and is independent of Phase 8–10. |
| `PG-AUD-SEC-006` | COMPLETE | CI permission minimization and immutable action pinning are current supply-chain controls. |
| `PG-AUD-SEC-007` | COMPLETE | Offline-pack data minimization applies to the current read-only offline MVP. |
| `PG-AUD-SEC-008` | COMPLETE | Release advisory fail-closed behavior can be enforced in current workflows. |

---

# C. Reliability, recovery and durable state

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-REL-001` | BLOCKED | Final acceptance requires real production database protection/backup capability and a restore drill against production-grade owner/repair data. Keep the runbook/gates; do not claim completion before the production infrastructure/cutover context exists. |
| `PG-AUD-REL-002` | COMPLETE | Durable photo outbox/reconciliation semantics are independently testable now. |
| `PG-AUD-REL-003` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Current serverless connection strategy is remediated. Expected-concurrency/load proof belongs with Phase 9/final hosted validation. |
| `PG-AUD-REL-004` | COMPLETE | Indeterminate-write recovery semantics are independently testable now. |
| `PG-AUD-REL-005` | COMPLETE | Provider/API/browser timeout hierarchy is a current path and was independently remediable. |
| `PG-AUD-REL-006` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Current narrow `operator_sync` ingestion is intentionally retained. Durable queue/backpressure implementation stays backlog until continuous/high-volume ingestion is scheduled. |
| `PG-AUD-REL-007` | BLOCKED | Structured telemetry/SLO/runbook implementation is complete, but final production-grade alert delivery is not. Resume only when an alert-capable hosting/backend decision exists in the appropriate hosted/production phase. |
| `PG-AUD-REL-008` | COMPLETE | Service-worker cache lifecycle is independent of Phase 8–10 and is fully remediated/proven at the current boundary. |

---

# D. Deployment, release and repository governance

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-DEP-001` | BLOCKED | Phase 10 cutover item. Requires Phase 9 completion, production-copy rehearsal, rollback proof, exact-green commit selection, and explicit authorization. |
| `PG-AUD-DEP-002` | COMPLETE | Vercel application builds are schema-read-only; migration execution is now a separate explicit operational action. Permanent CI/build self-checks prevent Alembic from returning to the Vercel build command. Production migration remains separately blocked by Phase 9/10 and explicit approval. |
| `PG-AUD-DEP-003` | BLOCKED | Branch protection requires an explicit repository-governance decision that preserves the standing direct-`main` roadmap bookkeeping workflow. |
| `PG-AUD-DEP-004` | BACKLOG | PR #84 remains an evolving consolidation/cutover artifact. Final synchronization belongs after remaining implementation/remediation and before Phase 10 merge review. |

`PG-AUD-DEP-002` proof:

- implementation proof head: `e826190b5872b6adab08c0376a8c280d7076c84d`
- Vercel build command contains no Alembic/database migration invocation
- `api/scripts/validate_vercel_migration_boundary.py` self-check passed in the exact-head Vercel build
- `api/scripts/validate_ci_security.py` independently enforces the same boundary in API CI
- explicit promotion/rollback contract: `docs/DATABASE_MIGRATION_PROMOTION_RUNBOOK.md`
- exact-head API CI/CD #928, Web CI/CD #791, Extraction Pipeline CI #247, Canonical Publication CI #199, Reference Repair Runtime CI #188, Database Reliability CI #51, Operational Observability CI #13, and Web Dependency Advisory Scan #55 passed
- exact-head Vercel deployment: `dpl_9jn3agBnytikvW9Nt93oesvcBsew` READY
- read-only post-deployment database verification: consolidation preview remained `0063_photo_storage_outbox`; production remained `0020_catalog_coverage`
- no database migration, production write, provider activation, publication, merge, or cutover was performed

---

# E. Frontend accessibility, reflow and browser behavior

Phase 8 is data-only by architecture, so concrete current-UI defects that can be implemented and tested against the existing UI remain eligible. Final cross-browser and assistive-technology campaign infrastructure belongs to Phase 9. When a current code control is complete but the original acceptance criteria require live browser/accessibility-tree/screen-reader proof, use `CURRENT CONTROL COMPLETE / FUTURE BACKLOG` rather than claiming final completion early.

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-UI-001` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Current programmatic-name defects are fixed and statically gated. Final browser accessibility-tree/axe/manual screen-reader proof remains Phase 9 validation work. |
| `PG-AUD-UI-002` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Sticky offsets now follow measured rendered header/navigation heights rather than fixed mobile pixels, and the contract is statically gated. Final 320px/zoom/text-scale/browser stress proof remains Phase 9 validation work. |
| `PG-AUD-UI-003` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Audited async workflow outcomes now feed shared polite/assertive live regions without focus movement, with duplicate-live-region suppression and CI coverage. Final real screen-reader announcement-once proof remains Phase 9 validation work. |
| `PG-AUD-UI-004` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Garage add-mode controls now use ordinary grouped toggle-button semantics with `aria-pressed`; final live accessibility-tree/keyboard verification remains Phase 9 work. |
| `PG-AUD-UI-005` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Settings Units and Text Size now use native same-name radio inputs in labeled fieldsets; final representative-browser/assistive-technology proof remains Phase 9 work. |
| `PG-AUD-UI-006` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | SPA route changes now update document titles, move focus to the new view context, expose a skip link, and honor reduced motion; final live browser/screen-reader validation remains Phase 9 work. |
| `PG-AUD-UI-007` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Repair Log photos can now reuse confirmed user-authored observations as equivalent descriptions without inventing image content or changing the database schema; final live accessibility validation and remaining photo-surface review remain Phase 9 work. |
| `PG-AUD-UI-008` | BACKLOG | Automated browser E2E/accessibility/cross-browser final regression gate is Phase 9 work. |
| `PG-AUD-UI-009` | BACKLOG | Final browser-support matrix enforcement depends on the Phase 9 representative-browser suite. |
| `PG-AUD-UI-010` | ELIGIBLE | Current contrast/target-size defects are concrete and independently measurable. |
| `PG-AUD-UI-011` | BLOCKED | Resolve the dead-code/import decision under `PG-AUD-CODE-003` first; if retained, accessibility proof can be scheduled with later browser/AT work. |

Current-control proof for `PG-AUD-UI-001` through `PG-AUD-UI-003`:

- `PG-AUD-UI-001`: Repair Log controls now have programmatic accessible names and Garage model year is associated with its visible label; `web/scripts/validate-accessible-form-labels.mjs` permanently gates the named controls.
- `PG-AUD-UI-002`: `ResizeObserver`-driven shell measurements feed sticky-stack CSS variables, replacing stale `46px`/`96px`/`98px` mobile assumptions; `web/scripts/validate-responsive-sticky-stack.mjs` guards the measured-offset contract.
- `PG-AUD-UI-003`: `AccessibleWorkflowAnnouncements.tsx` provides always-mounted polite `StatusMessage` and assertive `ErrorAlert` live regions, mirrors the audited Garage/Repair Log/Readiness/Start Repair/Completion message classes, skips messages already inside live regions, and does not move focus; `web/scripts/validate-accessible-workflow-announcements.mjs` guards the contract.
- shared exact proof head: `e9f79f48a80d70d6e0c3a19a807fed2e541b8133`
- exact-head API CI/CD #942, Web CI/CD #805, Extraction Pipeline CI #261, Canonical Publication CI #213, Reference Repair Runtime CI #202, Database Reliability CI #65, Operational Observability CI #27, and Web Dependency Advisory Scan #69 passed
- Web CI explicitly passed form-label, responsive sticky-stack, workflow-status-announcement, typecheck, production build, container build, and HTTP/security-header smoke steps
- exact-head Vercel deployment: `dpl_Gwu7DbFLy8rYCFH47H9XieZoTEz9` READY; its build also passed the schema-read-only Vercel migration boundary
- no database migration, production write, provider activation, publication, merge, or cutover was performed
- remaining browser accessibility-tree, axe, screen-reader, zoom/reflow and representative-browser acceptance proof stays in the existing Phase 9 backlog rather than being pulled forward

Current-control proof for `PG-AUD-UI-004` through `PG-AUD-UI-007`:

- `PG-AUD-UI-004`: Garage no longer advertises an incomplete tab pattern; the two add modes are a labeled button group with synchronized `aria-pressed` state, permanently gated by `web/scripts/validate-garage-mode-semantics.mjs`.
- `PG-AUD-UI-005`: Settings uses native radio semantics for both measurement units and text size, with labeled fieldsets, same-name inputs, and synchronized checked state; `web/scripts/validate-settings-radio-semantics.mjs` prevents custom incomplete radio semantics from returning.
- `PG-AUD-UI-006`: PartGraph route transitions update `document.title`, focus the new view heading/fallback main target after render, provide a keyboard-visible skip link, and avoid unconditional animation when reduced motion is requested; `web/scripts/validate-spa-navigation-accessibility.mjs` guards the contract.
- `PG-AUD-UI-007`: Repair Log photo upload can associate an existing confirmed user-authored observation through the already-supported nullable `observation_id`; that text becomes visible/equivalent image description, while unassociated legacy photos remain valid with an explicit no-user-description fallback and no generated visual claims. `web/scripts/validate-repair-photo-descriptions.mjs` guards the no-invention/association contract.
- shared exact proof head: `9c3c571edb18ad35ce26195131d8958c35272f5b`
- exact-head API CI/CD #958, Web CI/CD #821, Extraction Pipeline CI #277, Canonical Publication CI #229, Reference Repair Runtime CI #218, Database Reliability CI #81, Operational Observability CI #43, and Web Dependency Advisory Scan #85 passed
- Web CI explicitly passed Garage mode semantics, Settings radio semantics, SPA navigation accessibility, repair-photo description accessibility, the earlier UI accessibility contracts, typecheck, production build, container build, and HTTP/security-header smoke steps
- exact-head Vercel deployment: `dpl_J5j6S1J6n1GPZA2tfAoqjPkSh2GE` READY
- no database migration, production write, provider activation, publication, merge, or cutover was performed
- final accessibility-tree, keyboard/screen-reader, representative-browser, and complete photo-surface acceptance proof remains in the existing Phase 9 backlog rather than being pulled forward

---

# F. Codebase maintainability and dead/legacy paths

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-CODE-001` | BACKLOG | Retire compatibility bridges only after remaining functional work and final import usage are stable. |
| `PG-AUD-CODE-002` | BACKLOG | CSS consolidation depends on current accessibility/reflow fixes and later visual/browser regression. |
| `PG-AUD-CODE-003` | BACKLOG | Final dead-asset/import proof belongs after current UI work stabilizes; this also gates `PG-AUD-UI-011`. |
| `PG-AUD-CODE-004` | BLOCKED | Resolve only after current Readiness/UI cleanup establishes whether the hidden session bar is intentionally redundant or still needed. |

---

# G. Incomplete roadmap work through the Phase 7 boundary

Category G is roadmap-owned work, not a separate remediation implementation queue.

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-ROAD-001` | BACKLOG | Hosted durable-photo proof remains in its existing Phase 1/Phase 9 roadmap location. |
| `PG-AUD-ROAD-002` | BACKLOG | Deployed NHTSA operator HTTP proof remains unfinished Phase 6 roadmap work. |
| `PG-AUD-ROAD-003` | BACKLOG | Broad repair-knowledge population is Phase 6 breadth plus Phase 8 reference-fleet/data work. |

---

# H. Release/testing gates planned later

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-TEST-001` | BACKLOG | This is explicitly the Phase 9/final-release validation contract. Existing permanent CI remains active, but the final campaign waits for the functional MVP/fleet boundary it is intended to validate. |

---

## Execution consequence

The remediation queue skips all `BLOCKED` and `BACKLOG` items automatically.

At the current Phase 7 boundary, new audit-remediation implementation may come only from items marked `ELIGIBLE`, unless verified new evidence changes a dependency status. A task cannot be promoted from `BLOCKED`/`BACKLOG` merely because it is high priority or convenient to implement early.

Before changing any dependency status:

1. verify the exact live roadmap state;
2. verify the dependent code/data/infrastructure actually exists and is complete;
3. verify the change does not pull Phase 8, Phase 9, Phase 10, future provider scale, or production cutover work forward;
4. preserve PR #84 as draft/unmerged and production at its intentionally untouched boundary unless explicit authorization says otherwise.
