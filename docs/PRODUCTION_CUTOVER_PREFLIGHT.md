# PartGraph Production Cutover Preflight

Status: **NO-GO control for Phase 10. This document does not authorize Production mutation, PR #84 merge, provider activation, canonical publication, or branch deletion.**

Machine-readable contract: `ops/cutover/phase10_preflight_v1.json`  
Permanent contract test: `api/tests/test_phase10_preflight_contract.py`

## Purpose

The final Production decision must be based on one refreshed evidence package, not on scattered CI links, remembered branch state, or an assumption that a READY deployment is sufficient. This preflight combines the current source, database, deployment, disaster-recovery, rollback, and governance boundaries into one fail-closed checklist.

The checked-in JSON is a **dated observation plus policy contract**. It is not a reusable approval token. Before Production cutover, refresh every mutable observation against the exact candidate head and record the operator/owner approval separately.

## Current assessment — NO-GO

The implementation candidate is healthy, synchronized, and extensively validated, but Production promotion is still blocked.

Already proven:

- Phase 9 final validation is green at 18/18.
- The consolidation branch is 0 commits behind `main`.
- PR #84 is mergeable and remains draft/unmerged.
- A real isolated child of Production migrated from `0020_catalog_coverage` to `0063_photo_storage_outbox` while preserving every baseline owner/private table and all 35 persisted baseline rows.
- An isolated snapshot restore reproduced all 18 baseline owner/private tables and all 35 persisted rows.
- The rollback boundary is machine-checked: code-only rollback to the currently deployed Production application is unsafe after schema `0063`.
- Production remains at `0020_catalog_coverage`.

Current hard blockers:

1. **PG-AUD-REL-001 — Production backup/protection.** Production currently has no automatic snapshot schedule, six hours of point-in-time history, and no Neon branch protection. Restore mechanics are proven, but backup freshness/protection is not.
2. **PG-AUD-DEP-005 — deployment ordering.** The current Production Vercel deployment is sourced from commit `d68606162c725348779e2d4f93e8819eb8469f21`, and that Git commit changed only `docs/ROADMAP_LIVE.md`. This proves that a documentation-only `main` commit can produce a Production deployment. Because the old application is not safely writable against schema `0063`, PR merge, schema migration, and Production deployment cannot be allowed to happen in an uncontrolled order.
3. **PG-AUD-DEP-001 — explicit Production authorization.** Non-production Phase 10 work is authorized; Production mutation is not.

Two additional BLOCKED audit findings must be explicitly dispositioned in the final Production decision rather than silently ignored:

- **PG-AUD-REL-007:** alert definitions exist, but active alert delivery is not currently available/configured.
- **PG-AUD-DEP-003:** GitHub branch-protection governance remains unresolved; both `main` and the consolidation branch are currently unprotected.

## Preview-health nuance

The exact-head Vercel Preview deployment is READY. Its application readiness endpoint returned HTTP 200 earlier on 2026-09-20. A later unauthenticated probe returned HTTP 302 to Vercel SSO because Preview protection is active.

That 302 is not evidence that the PartGraph application is unhealthy, but it is also not an application-readiness pass. The final preflight must use an authorized Preview health probe and record the actual PartGraph readiness response.

Do not weaken Preview protection merely to make an unauthenticated preflight command return 200.

## Required final preflight sequence

All steps before the explicit approval point are read-only:

1. Freeze one exact candidate commit. Confirm the consolidation branch is 0 behind `main`, PR #84 points to that commit, and no newer commit appears during evidence collection.
2. Confirm all required exact-head CI workflows are completed successfully, including the 18-job MVP Final Validation suite and Database Reliability.
3. Confirm the exact candidate Vercel Preview is READY and perform an **authorized** `/api/v1/health/ready` check.
4. Confirm current Production deployment identity, `/api/v1/health/live`, `/api/v1/health/ready`, and the Production Alembic revision.
5. Re-run/read the Production backup/protection inspection. PG-AUD-REL-001 must be resolved by approved controls or an explicitly approved equivalent recovery design.
6. Record the Production deployment-order control. Because the application/schema rollback boundary is asymmetric, the plan must prevent an uncontrolled old-app/new-schema or new-app/old-schema window. This may be a separately authorized deployment-trigger control or an explicitly approved maintenance/write-freeze procedure.
7. Record the disposition of PG-AUD-REL-007 and PG-AUD-DEP-003.
8. Reconfirm the isolated Production-copy migration proof, owner-state preservation proof, restore proof, and `ops/cutover/phase10_rollback_v1.json`.
9. Record the exact migration range, intended after revision, post-migration checks, smoke-test scope, and coordinated rollback/forward-fix path.
10. Only then may the project owner explicitly authorize Production migration/cutover for that exact candidate and evidence package.

If any mutable fact changes after approval but before execution, stop and refresh the preflight. Approval for one commit/environment state does not carry forward automatically.

## Cutover-order constraint

Do not infer a safe order from Vercel's normal Git integration.

The currently deployed Production application was built from a documentation-only `main` commit, demonstrating that merge/main activity can trigger Production deployment. Meanwhile:

- Production database is still at `0020_catalog_coverage`;
- the candidate expects the current schema through `0063_photo_storage_outbox`;
- the old Production photo-write path cannot safely write against `0063`;
- a simple Vercel application rollback after schema promotion is therefore not a safe rollback.

The final plan must explicitly control the interval in which schema and application are promoted. Do not merge PR #84 merely to discover what Vercel does.

The prepared sequence is now defined in `docs/PRODUCTION_CUTOVER_CHOREOGRAPHY.md` and `ops/cutover/phase10_cutover_choreography_v1.json`. It stages an exact Production-target candidate with no domain, requires a proven traffic barrier, migrates/verifies while traffic is blocked, then promotes and verifies the candidate before reopening traffic. The barrier itself remains intentionally unselected until the required Production-governance authorization and capability proof exist.

## Evidence record

The eventual cutover record must retain, without credentials:

- exact candidate Git SHA;
- PR #84 base/head state;
- exact CI run IDs;
- exact Preview and Production deployment IDs;
- authorized readiness results;
- Production Neon branch ID and before/after Alembic revisions;
- backup/protection and restore evidence;
- production-copy preservation evidence;
- deployment-order/maintenance control used;
- rollback/forward-fix decision;
- operator identity;
- project-owner approval and timestamp.

The record must never contain database connection strings, provider credentials, session cookies, Vercel bypass tokens, GitHub tokens, or Neon API keys.
