# PartGraph Audit Status

Status: **Phase 0–9 remediation closed at the current roadmap boundary.**  
Date: **2026-09-19**  
Canonical architecture: `docs/BLUEPRINT.md`  
Roadmap: `docs/ROADMAP.md`

## Current result

The remediation audit has **0 decision-free ELIGIBLE items**.

There are **18 intentionally deferred items**:

- **5 BLOCKED**
- **5 BACKLOG**
- **8 CURRENT CONTROL COMPLETE / FUTURE BACKLOG**

Completed-finding narratives, intermediate CI run IDs, and remediation work logs were removed from the active documentation tree to reduce stale context. They remain available in Git history.

## Deferred register

| Finding | Status | Reopen condition |
| --- | --- | --- |
| PG-AUD-REL-001 | BLOCKED | Production-grade database protection/backup capability exists and a restore drill can be run against representative owner/repair data. |
| PG-AUD-REL-007 | BLOCKED | An alert-capable production hosting/observability backend is selected so delivery can be activated and tested. |
| PG-AUD-DEP-001 | BLOCKED | Explicit Phase 10 authorization plus production DR/rollback/environment readiness. |
| PG-AUD-DEP-003 | BLOCKED | Explicit repository-governance decision for branch protection that preserves the intended documentation workflow. |
| PG-AUD-DEP-005 | BLOCKED | Explicit deployment-governance authorization to change Production deploy-trigger behavior for documentation-only commits. |
| PG-AUD-DEP-004 | BACKLOG | Final PR #84 synchronization immediately before authorized Phase 10 review. |
| PG-AUD-UI-008 | BACKLOG | Post-MVP axe-style accessibility scanning, broader browser coverage, and manual screen-reader evidence are scheduled. |
| PG-AUD-UI-009 | BACKLOG | A supported-browser/version policy is defined and Firefox/WebKit enforcement is scheduled. |
| PG-AUD-ROAD-002 | BACKLOG | An authorized deployed non-production operator execution path is available for the real NHTSA HTTP proof. |
| PG-AUD-ROAD-003 | BACKLOG | Broad canonical repair-knowledge population resumes. |
| PG-AUD-SEC-004 | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | A stored provider URL becomes executable by a future adapter; revalidate outbound-network protections then. |
| PG-AUD-REL-003 | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Serverless concurrency materially increases or an external transaction pooler is introduced. |
| PG-AUD-REL-006 | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Continuous/high-volume ingestion is scheduled; then add durable queue/backpressure behavior. |
| PG-AUD-UI-002 | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Broader 320px/zoom/text-scale/multi-browser stress becomes release scope. |
| PG-AUD-UI-003 | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Manual real-screen-reader announcement evidence becomes release scope. |
| PG-AUD-UI-007 | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Broader live accessibility/photo-surface review becomes release scope. |
| PG-AUD-UI-010 | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Exhaustive state/contrast/touch-target multi-browser review becomes release scope. |
| PG-AUD-CODE-002 | CURRENT CONTROL COMPLETE / FUTURE BACKLOG | Broad design-token/active-cascade consolidation is paired with later visual/multi-browser hardening. |

## Repository-hygiene review

The 2026-09-19 full-tree hygiene pass reviewed all tracked files for stale coding-agent artifacts, duplicated documentation, dead compatibility/future abstractions, orphan assets, dependency bloat, and generated/legacy data.

Removed from the active tree:

- abandoned hosted-NHTSA proof harness/test that could not execute without an authorized Preview operator session;
- `api/partgraph/assistance/models.py`, a temporary “Block 12A / five-PR restructuring” compatibility shim with no current consumer;
- `api/partgraph/intelligence/contracts.py`, an unused future model-gateway abstraction whose consumers had already been removed;
- unreferenced `docs/partgraph_vehicle_test_1996_2000.xlsx`;
- duplicated `ROADMAP_LIVE.md`;
- the former large Phase 0–9 audit report and execution-gate working documents, replaced by this compact register.

Intentionally retained after dependency proof:

- `api/data/Selected_Asian_Brands_1996_2000.xlsx`, because immutable migrations reconstruct the historical lineage from that exact path;
- legacy equipment generator modules used by immutable migrations 0027–0029 and parity tests;
- migration baseline chunks and all Alembic history;
- all web validation scripts currently invoked by CI;
- current explicit Python and web dependencies; no third-party package was proven unused safely enough to remove.

## Execution rule

Do not implement BLOCKED, BACKLOG, or FUTURE BACKLOG items simply because they exist. Reclassify only when the documented dependency becomes true or the project owner explicitly changes the boundary.

Repository hygiene does not authorize Production mutation, Phase 10, PR #84 merge, branch deletion, provider activation, or canonical-data publication.
