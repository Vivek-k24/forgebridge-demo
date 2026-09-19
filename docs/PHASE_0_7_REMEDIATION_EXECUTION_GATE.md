# PartGraph Phase 0–9 Remediation Execution Gate

Status: **Authoritative execution-status overlay for `docs/PHASE_0_7_AUDIT_REMEDIATION_REPORT.md`, re-audited through the completed Phase 9 boundary.**

This file does not change the audit findings, architecture, roadmap order, or acceptance criteria. It prevents remediation work from pulling Phase 10, unfinished Phase 6 breadth/provider work, future-provider scale, post-MVP browser/accessibility hardening, production infrastructure, or still-unresolved cross-task work forward prematurely.

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
- Phase 8 five-model reference fleet: complete.
- Phase 9 final MVP validation campaign: complete on exact clean head `5a95001b594e14437492dd131d41f519619a0eff`; MVP Final Validation CI #205 passed all 18 jobs.
- Phase 1 hosted durable-photo persistence proof: complete on Vercel Preview `dpl_7qkpKhUL7Yui3rT3Npvwg8kh3PCN`.
- Phase 10 production MVP cutover: not started and requires explicit production approval.
- Phase 6 deployed NHTSA HTTP proof and broad canonical repair-knowledge population: still pending.

If an item depends on Phase 10, unfinished Phase 6 work, unavailable production infrastructure, an explicit owner/governance decision, future provider scale, or another unfinished remediation item, it remains blocked/backlog rather than being implemented speculatively.

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
| `PG-AUD-REL-003` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Phase 9 now proves the current `NullPool` strategy with 24 parallel serverless-shaped instances and verifies no idle pool multiplier remains. Revalidate only if intended concurrency materially rises or an external transaction pooler is introduced. |
| `PG-AUD-REL-004` | COMPLETE | Indeterminate-write recovery semantics are independently testable now. |
| `PG-AUD-REL-005` | COMPLETE | Provider/API/browser timeout hierarchy is a current path and was independently remediable. |
| `PG-AUD-REL-006` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Current narrow `operator_sync` ingestion is intentionally retained. Durable queue/backpressure implementation stays backlog until continuous/high-volume ingestion is scheduled. |
| `PG-AUD-REL-007` | BLOCKED | Structured telemetry/SLO/runbook implementation is complete, but final production-grade alert delivery is not. Resume only when an alert-capable hosting/backend decision exists in the appropriate hosted/production phase. |
| `PG-AUD-REL-008` | COMPLETE | Service-worker cache lifecycle is independent of Phase 8–10 and is fully remediated/proven at the current boundary. |
| `PG-AUD-REL-009` | ELIGIBLE | Phase 9 exposed an independent offline-pack refresh race: overlapping sync triggers can let a stale response rewrite the cached authoritative timestamp during offline transition. Fix now with generation-aware/coalesced synchronization; no Phase 10 or production dependency exists. |

---

# D. Deployment, release and repository governance

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-DEP-001` | BLOCKED | Phase 9 and production-copy rehearsal are complete, but the actual Phase 10 cutover still requires production DR/rollback readiness, exact-green commit selection, environment verification, and explicit authorization. |
| `PG-AUD-DEP-002` | COMPLETE | Vercel application builds are schema-read-only; migration execution is now a separate explicit operational action. Permanent CI/build self-checks prevent Alembic from returning to the Vercel build command. Production migration remains separately blocked by Phase 9/10 and explicit approval. |
| `PG-AUD-DEP-003` | BLOCKED | Branch protection requires an explicit repository-governance decision that preserves the standing direct-`main` roadmap bookkeeping workflow. |
| `PG-AUD-DEP-004` | BACKLOG | PR #84 remains an evolving consolidation/cutover artifact. Final synchronization belongs after the remaining Phase 6/remediation work and immediately before Phase 10 merge review. |
| `PG-AUD-DEP-005` | BLOCKED | Documentation-only `main` commits currently trigger Production Vercel builds. A path-aware Production deploy-skip rule is a deployment-governance/Phase 10 change and requires explicit authorization before changing Production project behavior. |

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

Phase 8 and the intended Phase 9 Chromium validation are complete. Concrete UI defects already fixed remain complete/current-control complete. Broader multi-browser, axe-style accessibility scanning, zoom/reflow stress, and manual screen-reader sign-off were not part of the finished Phase 9 Chromium gate and remain post-MVP backlog rather than being retroactively pulled into Phase 9.

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-UI-001` | COMPLETE | The named programmatic-label defects are fixed and permanently statically gated. Broader automated/manual accessibility auditing remains tracked under UI-008 rather than reopening this specific defect. |
| `PG-AUD-UI-002` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Measured sticky offsets replace fixed mobile pixels and are statically gated. Full 320px/zoom/text-scale/multi-browser stress remains post-MVP UI-008/UI-009 backlog. |
| `PG-AUD-UI-003` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Shared polite/assertive live regions and duplicate suppression are implemented and statically gated. Manual real-screen-reader announcement-once proof remains post-MVP accessibility backlog. |
| `PG-AUD-UI-004` | COMPLETE | Garage add-mode controls use ordinary grouped toggle-button semantics with synchronized `aria-pressed`, and the incomplete tab contract is permanently guarded against regression. |
| `PG-AUD-UI-005` | COMPLETE | Settings Units and Text Size use native same-name radio inputs in labeled fieldsets; the original custom-radio semantic defect is removed and statically gated. |
| `PG-AUD-UI-006` | COMPLETE | SPA route changes update titles, move focus to the destination context, expose a skip link, honor reduced motion, and the Phase 9 real Chromium browser gate verifies title/focus behavior. |
| `PG-AUD-UI-007` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | User-authored observations can provide equivalent photo descriptions without generated visual claims. Broader live accessibility/photo-surface review remains post-MVP backlog. |
| `PG-AUD-UI-008` | BACKLOG | Phase 9 added permanent real Chromium E2E, offline/degraded, and timeout/recovery browser gates. Axe-style automated accessibility scanning, multi-browser coverage, and manual screen-reader release evidence remain post-MVP hardening. |
| `PG-AUD-UI-009` | BACKLOG | The shipped Phase 9 browser contract is Chromium-only. An explicit supported-browser/version matrix plus Firefox/WebKit enforcement remains a later product/support-policy task. |
| `PG-AUD-UI-010` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | The named contrast and primary touch-target defects are corrected and measured/gated. Exhaustive state/contrast/multi-browser inventory remains post-MVP accessibility backlog. |
| `PG-AUD-UI-011` | COMPLETE | `YearWheel.tsx` was proven unused and retired; no custom spinbutton remains to require assistive-technology sign-off. |

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

Current-control proof for `PG-AUD-UI-010`:

- `accessibility-ui.css` now raises the audited repair placeholder and named Home muted strings to `--pg-dark-muted-text: #82979e`; across the audited dark backgrounds (`#0f1a20`, `#132126`, `#16262b`) the permanent validator calculates a minimum contrast of 5.10:1, above the 4.5:1 ordinary-text target.
- standalone primary touch controls use `--pg-primary-touch-target: 44px`; the inventory voice-search mic is now 44×44 minimum, while compact inline controls are not enlarged indiscriminately.
- `web/scripts/validate-current-contrast-targets.mjs` calculates relative-luminance contrast, guards the named selectors, enforces the 44px primary-target floor, and verifies `accessibility-ui.css` remains loaded after the older repair contrast layer.
- exact implementation proof head: `c98e17fbe73f75c30fecc942f3889f86a83f0fa9`
- exact-head API CI/CD #962, Web CI/CD #825, Extraction Pipeline CI #281, Canonical Publication CI #233, Reference Repair Runtime CI #222, Database Reliability CI #85, Operational Observability CI #47, and Web Dependency Advisory Scan #89 passed
- Web CI explicitly passed the new calculated contrast/target-size gate, all earlier UI accessibility contracts, typecheck, production build, container build, and HTTP/security-header smoke steps
- exact-head Vercel deployment: `dpl_2F7YemQVnb7MSbgU5LuWu9hYXSWR` READY; its build passed the schema-read-only Vercel migration boundary before building the application
- no database migration, production write, provider activation, publication, merge, or cutover was performed
- the exhaustive contrast inventory, interactive-state measurement, representative-browser checks, and manual visual/accessibility validation remain in the existing Phase 9 backlog rather than being pulled forward

---

# F. Codebase maintainability and dead/legacy paths

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-CODE-001` | COMPLETE | The four audited compatibility-only packages were removed after remaining consumers were migrated to canonical modules. `api/tests/test_retired_compatibility_bridges.py` permanently rejects retired packages/imports; exact head `a1c868b39bc2ff6044093a172a761a2d5883df68` passed API CI #1103, Reference Repair Runtime #394, MVP Final Validation #235, all other exact-head regression workflows, and a READY Preview deployment. |
| `PG-AUD-CODE-002` | BACKLOG | The current accessibility/reflow fixes are stable, but broad stylesheet/cascade consolidation is maintainability work best paired with the later visual/multi-browser regression effort. |
| `PG-AUD-CODE-003` | COMPLETE | Dependency proof completed; `YearWheel.tsx` and `production-launch.css` were removed and `web/scripts/validate-retired-frontend-assets.mjs` prevents their return. |
| `PG-AUD-CODE-004` | COMPLETE | The hidden Readiness session/lease subtree, dead selector/lease handlers, and stale styles were removed on `3bc78cf918cd9957beab0597b30c17da6f7b841f`; the retired-frontend guard, Web CI #956, Phase 9 Final Validation #215, and READY Preview prove the cleanup. |

---

# G. Incomplete roadmap work through the Phase 9 boundary

Category G is roadmap-owned work, not a separate remediation implementation queue.

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-ROAD-001` | COMPLETE | Exact-head Vercel Preview private-Blob write, forced local-cache loss, rehydration/byte verification, and deletion all passed; the Phase 1/9 hosted durability gate is closed. |
| `PG-AUD-ROAD-002` | BACKLOG | Deployed NHTSA operator HTTP proof remains unfinished Phase 6 roadmap work. |
| `PG-AUD-ROAD-003` | BACKLOG | Phase 8 reference-fleet proof is complete, but broad canonical repair-knowledge population remains genuine unfinished Phase 6 breadth work. |

---

# H. Release/testing gates planned later

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-TEST-001` | COMPLETE | Phase 9 now has permanent jobs for every Blueprint final-validation layer named by this finding, and MVP Final Validation CI #205 passed all 18 jobs on the exact clean head. |

---

## Execution consequence

The remediation queue skips all `BLOCKED` and `BACKLOG` items automatically.

At the completed Phase 9 boundary, new audit-remediation implementation may come only from items marked `ELIGIBLE`, unless verified new evidence changes a dependency status. After closing `PG-AUD-CODE-004` and the now-proven-independent `PG-AUD-CODE-001`, there is currently no remaining decision-free `ELIGIBLE` item: the unresolved register consists of `BLOCKED`, `BACKLOG`, or `CURRENT CONTROL COMPLETE / FUTURE BACKLOG` work. A task cannot be promoted from those states merely because it is high priority or convenient to implement early.

Before changing any dependency status:

1. verify the exact live roadmap state;
2. verify the dependent code/data/infrastructure actually exists and is complete;
3. verify the change does not pull Phase 10, unfinished Phase 6 breadth/provider work, future provider scale, post-MVP support-policy work, or production cutover work forward;
4. preserve PR #84 as draft/unmerged and production at its intentionally untouched boundary unless explicit authorization says otherwise.