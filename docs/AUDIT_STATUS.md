# PartGraph Audit Status

Status: **Phase 0–9 remediation closed at the current roadmap boundary.**  
Date: **2026-09-19**  
Canonical architecture: `docs/BLUEPRINT.md`  
Roadmap: `docs/ROADMAP.md`

## Current result

The remediation audit has **0 decision-free ELIGIBLE items**.

There are **17 intentionally deferred items**:

- **5 BLOCKED**
- **4 BACKLOG**
- **8 CURRENT CONTROL COMPLETE / FUTURE BACKLOG**

Completed-finding narratives, intermediate CI run IDs, and remediation work logs were removed from the active documentation tree to reduce stale context. They remain available in Git history.

`PG-AUD-DEP-004` closed on 2026-09-20: `main` was merged into `partgraph-mvp-consolidation` after verifying that the 22 intervening `main` commits changed only the superseded `docs/ROADMAP_LIVE.md`. The synchronization merge preserved that file's deliberate hygiene deletion, and the consolidation branch is now 0 commits behind `main`.

## Deferred register

| Finding | Status | Reopen condition |
| --- | --- | --- |
| PG-AUD-REL-001 | BLOCKED | Restore mechanics are proven on an isolated Neon snapshot restore. Reopen for completion when an approved Production backup/freshness policy is configured and verified; Production currently has no automatic snapshot schedule and project point-in-time history retention is 6 hours. |
| PG-AUD-REL-007 | BLOCKED | An alert-capable production hosting/observability backend is selected so delivery can be activated and tested. |
| PG-AUD-DEP-001 | BLOCKED | Phase 10 non-production preparation is authorized and the fail-closed preflight mechanism exists. Current preflight is NO-GO; Production cutover remains blocked pending the required hard gates/decision dispositions in `ops/cutover/phase10_preflight_v1.json` and separate explicit Production authorization. |
| PG-AUD-DEP-003 | BLOCKED | Explicit repository-governance decision for branch protection that preserves the intended documentation workflow. |
| PG-AUD-DEP-005 | BLOCKED | Explicit deployment-governance authorization to change Production deploy-trigger behavior for documentation-only commits. |
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

Additional full-tree cleanup completed in the same hygiene pass:

- collapsed import-only identity infrastructure bridges (`identity/config.py`, `identity/database.py`, `identity/errors.py`) into direct root-module imports;
- collapsed repair-experience auth/config/error/model compatibility shims into canonical imports;
- extended the compatibility regression guard so those shim paths cannot return silently;
- removed stale Database Reliability workflow references to the deleted identity database bridge;
- scanned all 124 runtime Python modules, 59 tests, 65 migrations, 13 API scripts, 12 frontend validators, 35 JSON assets, 10 workflows, Markdown documentation, and remaining root/config templates for stale paths, TODO/FIXME/stub scaffolding, placeholder/mock data, duplicate blobs, backup files, and generated caches;
- verified all declared Python and web dependencies still have active consumers.

Measured cleanup reduction at commit `d1354df578fcad7e41ffe67fb9fb7de0f4f77933`, relative to the pre-hygiene head `f93b813767246ced3c66c2310e22a6d915bfe71e`:

- files: **413 → 398**;
- tracked bytes: **2,795,700 → 2,624,599** (**171,101 bytes removed**);
- documentation bytes: **218,973 → 68,619** (**150,354 bytes removed**);
- API bytes: **2,040,490 → 2,020,203** (**20,287 bytes removed**);
- web source/package footprint: unchanged because every tracked frontend module, stylesheet, validator, and dependency remained live.

These figures are a fixed measurement checkpoint, not a claim about the byte count of later commits. Subsequent commits added this audit-status detail and corrected import ordering/canonical import paths without restoring the removed scaffolding or documentation.

Intentionally retained after dependency proof:

- `api/data/Selected_Asian_Brands_1996_2000.xlsx`, because immutable migrations reconstruct the historical lineage from that exact path;
- legacy equipment generator modules used by immutable migrations 0027–0029 and parity tests;
- migration baseline chunks and all Alembic history;
- all web validation scripts currently invoked by CI;
- current explicit Python and web dependencies; no third-party package was proven unused safely enough to remove.

## Execution rule

Do not implement BLOCKED, BACKLOG, or FUTURE BACKLOG items simply because they exist. Reclassify only when the documented dependency becomes true or the project owner explicitly changes the boundary.

Repository hygiene does not authorize Production mutation, Phase 10, PR #84 merge, branch deletion, provider activation, or canonical-data publication.
