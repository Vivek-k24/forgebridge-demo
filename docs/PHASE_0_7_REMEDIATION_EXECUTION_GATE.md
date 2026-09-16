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
- Phase 1 hosted durable-photo persistence proof: still pending and explicitly tied to the later hosted/final validation work.
- Phase 6 deployed NHTSA HTTP proof and broad canonical repair-knowledge population: still pending.

If an item depends on any of those unfinished tasks, or on another unfinished remediation item, it must remain blocked/backlog rather than being implemented speculatively.

---

# A. Data model, schema and canonical-data integrity

All Category A work was completed before this execution gate and has current-phase proof. No Phase 8–10 dependency needs to be pulled forward.

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
| `PG-AUD-SEC-004` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Existing generic outbound-network protection may remain, but **no additional generic-provider/adapter-specific SSRF work is to be invented now**. Revalidate only when a stored provider URL actually becomes executable by a future adapter. Current fixed NHTSA behavior remains the active path. |
| `PG-AUD-SEC-005` | COMPLETE | Photo decode/file hardening is a current upload boundary and is independent of Phase 8–10. |
| `PG-AUD-SEC-006` | COMPLETE | CI permission minimization and immutable action pinning are current supply-chain controls. |
| `PG-AUD-SEC-007` | COMPLETE | Offline-pack data minimization applies to the current read-only offline MVP. |
| `PG-AUD-SEC-008` | COMPLETE | Release advisory fail-closed behavior can be enforced in the current workflows without waiting for final cutover. |

---

# C. Reliability, recovery and durable state

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-REL-001` | BLOCKED | Final acceptance requires real production database protection/backup capability and a restore drill against production-grade owner/repair data. Keep the runbook/gates, but do not claim remediation complete before the production infrastructure/cutover context exists. |
| `PG-AUD-REL-002` | COMPLETE | Durable photo outbox/reconciliation semantics are independently testable now. |
| `PG-AUD-REL-003` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Current serverless connection strategy is remediated. Any final expected-concurrency/load proof belongs with Phase 9/final hosted validation; do not create a premature scale campaign now. |
| `PG-AUD-REL-004` | COMPLETE | Indeterminate-write recovery semantics are independently testable now. |
| `PG-AUD-REL-005` | COMPLETE | Provider/API/browser timeout hierarchy is a current path and was independently remediable. |
| `PG-AUD-REL-006` | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Current narrow `operator_sync` ingestion is intentionally retained. Durable queue/backpressure implementation is **backlog until continuous/high-volume ingestion is actually scheduled**. The present scale gate exists specifically to prevent premature activation. |
| `PG-AUD-REL-007` | BLOCKED | Structured telemetry/SLO/runbook implementation is complete, but final production-grade alert delivery is not. Do not add another monitoring stack merely to close the audit. Resume only when an alert-capable hosting/backend decision exists in the appropriate hosted/production phase. |
| `PG-AUD-REL-008` | COMPLETE | Service-worker cache lifecycle is independent of Phase 8–10 and is fully remediated/proven at the current boundary. |

---

# D. Deployment, release and repository governance

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-DEP-001` | BLOCKED | This is a Phase 10 production-cutover blocker. It requires Phase 9 completion, production-copy rehearsal, rollback proof, exact-green commit selection, and explicit authorization. Do not execute it now. |
| `PG-AUD-DEP-002` | ELIGIBLE | Decoupling schema migration from application build is a pre-cutover safety improvement and does not require Phase 8/9/10 completion. |
| `PG-AUD-DEP-003` | BLOCKED | Branch protection requires an explicit repository-governance decision that preserves the standing direct-`main` roadmap bookkeeping workflow and does not accidentally block authorized maintenance. Do not change repository rules until that policy is resolved. |
| `PG-AUD-DEP-004` | BACKLOG | PR #84 is still an evolving consolidation/cutover artifact. Final synchronization of its proof/status belongs after remaining implementation/remediation and before Phase 10 merge review; repeatedly rewriting it now would immediately become stale again. |

---

# E. Frontend accessibility, reflow and browser behavior

Phase 8 is data-only by architecture, so concrete current-UI defects that can be implemented and tested against the existing browser UI remain eligible. Final cross-browser campaign infrastructure belongs to Phase 9.

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-UI-001` | ELIGIBLE | Programmatic labels are a concrete current UI defect. |
| `PG-AUD-UI-002` | ELIGIBLE | Sticky/reflow behavior can be fixed and stress-tested on the current UI. |
| `PG-AUD-UI-003` | ELIGIBLE | Current asynchronous status announcements can be fixed independently. |
| `PG-AUD-UI-004` | ELIGIBLE | Incorrect tab semantics are a concrete current UI defect. |
| `PG-AUD-UI-005` | ELIGIBLE | Incorrect radio-group behavior is a concrete current UI defect. |
| `PG-AUD-UI-006` | ELIGIBLE | SPA focus/orientation behavior is a current navigation defect. |
| `PG-AUD-UI-007` | ELIGIBLE | Current repair-photo accessible-description model can be corrected without later fleet work. |
| `PG-AUD-UI-008` | BACKLOG | Automated browser E2E/accessibility/cross-browser **final regression gate is Phase 9 work**. Do not build the final campaign while Phase 8 and other current UI remediation remain unfinished. |
| `PG-AUD-UI-009` | BACKLOG | Final browser-support matrix enforcement depends on the Phase 9 representative-browser suite. Policy may be discussed, but do not claim closure until the suite exists. |
| `PG-AUD-UI-010` | ELIGIBLE | Current contrast/target-size defects are concrete and independently measurable. |
| `PG-AUD-UI-011` | BLOCKED | Do not independently redesign/prove the unused `YearWheel`. First resolve the dead-code/import decision under `PG-AUD-CODE-003`; if it is retained, accessibility proof can then be scheduled with the browser/AT work. |

---

# F. Codebase maintainability and dead/legacy paths

Maintainability cleanup must not delete or reorganize code that later roadmap/UI work may still touch. These items are therefore intentionally sequenced behind functional/accessibility stabilization rather than being treated as urgent cleanup.

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-CODE-001` | BACKLOG | Retire compatibility bridges only after remaining functional work and final import usage are stable; avoid churn before Phase 8/9 completion. |
| `PG-AUD-CODE-002` | BACKLOG | CSS consolidation depends on current accessibility/reflow fixes and the later visual/browser regression gate. Clean the cascade only after those behaviors stabilize. |
| `PG-AUD-CODE-003` | BACKLOG | Run final dead-asset/import proof after current UI work stabilizes; removal belongs to late cleanup, not before unfinished UI/browser work. This also gates `PG-AUD-UI-011`. |
| `PG-AUD-CODE-004` | BLOCKED | Resolve only after the current Readiness/UI cleanup establishes whether the hidden session bar is intentionally redundant or still needed. Do not delete it in isolation. |

---

# G. Incomplete roadmap work through the Phase 7 boundary

Category G is **roadmap-owned work, not a separate remediation implementation queue**. These findings remain visible so they are not forgotten, but remediation must not duplicate or reorder their roadmap execution.

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-ROAD-001` | BACKLOG | Hosted durable-photo proof remains in its existing Phase 1/Phase 9 roadmap location. Do not manufacture a separate remediation path. |
| `PG-AUD-ROAD-002` | BACKLOG | Deployed NHTSA operator HTTP proof remains unfinished Phase 6 roadmap work. Complete it through the Phase 6 path, not as an audit side quest. |
| `PG-AUD-ROAD-003` | BACKLOG | Broad repair-knowledge population is Phase 6 breadth plus Phase 8 reference-fleet/data work. Keep it data-only and resume through the roadmap. |

---

# H. Release/testing gates planned later

| Item | Execution status | Dependency decision |
| --- | --- | --- |
| `PG-AUD-TEST-001` | BACKLOG | This is explicitly the Phase 9/final-release validation contract. Existing permanent CI stays active, but the final browser/randomized/reference-fleet/production-copy campaign must wait for the functional MVP/fleet boundary it is intended to validate. |

---

## Execution consequence

The remediation queue must now skip all `BLOCKED` and `BACKLOG` items automatically.

At the current Phase 7 boundary, the next audit-remediation work may come only from items marked `ELIGIBLE`, unless new evidence changes a dependency status. A task cannot be promoted from `BLOCKED`/`BACKLOG` merely because it is high priority or because implementing it early seems convenient.

Before changing any dependency status:

1. verify the exact live roadmap state;
2. verify the dependent code/data/infrastructure actually exists and is complete;
3. verify the change does not pull Phase 8, Phase 9, Phase 10, future provider scale, or production cutover work forward;
4. preserve PR #84 as draft/unmerged and production at its intentionally untouched boundary unless explicit authorization says otherwise.
