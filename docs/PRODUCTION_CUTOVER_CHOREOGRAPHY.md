# PartGraph Production Cutover Choreography

Status: **prepared but not authorized.** This runbook designs the safe ordering for Phase 10. It does not authorize PR #84 merge, Production migration, Vercel Production changes, traffic blocking, provider activation, or canonical publication.

Machine-readable contract: `ops/cutover/phase10_cutover_choreography_v1.json`  
Permanent contract test: `api/tests/test_phase10_cutover_choreography.py`

## Why a traffic barrier is required

The current Production application expects the old `0020_catalog_coverage` database behavior. The candidate database reaches `0063_photo_storage_outbox`, where photo writes require an explicit durable storage state that the old application does not supply.

That creates one dangerous interval: after the database is migrated but before the candidate application is live. Public writes must not be allowed during that interval.

A normal Vercel Git deployment is not an adequate ordering control because current evidence shows a documentation-only `main` commit produced a Production deployment.

## Selected architecture

The cutover uses a staged candidate plus a temporary traffic barrier:

1. Build the exact approved candidate with Production environment variables using Vercel's Production target, but use `--skip-domain` so it receives no Production traffic.
2. Activate a separately approved traffic barrier and prove public requests are blocked.
3. Capture/verify the immediate pre-migration recovery point.
4. Upgrade Production from `0020_catalog_coverage` to the exact repository Alembic head.
5. Verify database revision and owner/private preservation while traffic is still blocked.
6. Test the already-built candidate directly against the migrated Production database using authorized health/read-only checks.
7. Promote that exact deployment to Production while the barrier remains active.
8. Verify the promoted deployment through the authorized barrier bypass.
9. Reopen public traffic only after everything passes.

This keeps the old Production deployment available until the database and candidate have both been verified.

## Allowed traffic barriers

No barrier is selected yet. Selection is a Production-governance decision.

### Option A: Vercel Authentication for all traffic

Vercel documents a project protection mode that can require Vercel Authentication for all deployments/Production traffic. Before using it, the operator must prove that this control is available on the current PartGraph plan and record an authorized bypass method for health checks.

Required proof:

- an unauthenticated Production request is blocked before migration;
- an authorized operator health request still succeeds;
- disabling the protection after cutover is understood and recorded.

### Option B: dedicated maintenance deployment

A separately verified maintenance deployment can temporarily own the Production domain while the real candidate remains unaliased.

The maintenance deployment must have no PartGraph database mutation path. It is not the candidate application with a hopeful configuration toggle.

## Rejected shortcuts

Do not:

- deploy the new application publicly before the database is ready;
- migrate the database while the old public application can still accept writes;
- depend on a new environment flag that does not exist in the currently deployed application;
- revoke broad PostgreSQL privileges ad hoc and try to reconstruct them during an incident;
- automatically run Alembic downgrade;
- merge PR #84 first and let normal Vercel Git behavior determine the order;
- remove the traffic barrier before database and candidate verification finish.

## Failure handling

Before public traffic is reopened, failure is comparatively simple because no new public writes should exist.

If migration or candidate verification fails:

1. keep the traffic barrier active;
2. determine whether the database remained at `0020`, advanced transactionally, or reached the new head;
3. use a reviewed forward correction when clearly safe;
4. otherwise restore the approved pre-migration recovery point;
5. only after the old database/application pair is re-established may the old Production deployment receive public traffic again.

After public traffic is reopened, a database restore can lose post-cutover writes. Forward correction becomes the preferred response unless a coordinated restore is explicitly approved with its data-loss implications understood.

## PR/main reconciliation

The production artifact and Git branch history are related but distinct controls. Do not use PR merge as the mechanism that chooses the Production deployment.

After the verified candidate is serving Production, reconcile PR #84/`main` under the approved deployment-governance policy. If that reconciliation causes Vercel to create another Production deployment, do not allow it to replace the already-verified artifact unless its commit/tree/environment are proven equivalent and the normal readiness checks pass.
