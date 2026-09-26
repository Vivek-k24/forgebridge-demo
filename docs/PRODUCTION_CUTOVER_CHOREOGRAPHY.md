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

## Selected traffic barrier

The selected barrier is **Vercel Authentication with scope = All Deployments**.

Vercel announced on 2026-09-09 that Vercel Authentication can protect all project deployments, including the Production domain, at no additional cost on every plan. This removes the earlier plan uncertainty for the current PartGraph Hobby project.

Selection does **not** authorize activation. Production must remain public until the explicit cutover authorization.

Before activation, capture the exact existing protection state:

```bash
vercel project protection partgraph-main --format json
```

Store that output in the operator evidence record without credentials.

At the approved freeze step, use Vercel's Update Project API so the intended scope is explicit:

```http
PATCH /v9/projects/prj_hDThLALewtC4I4nvGNVyFeY0iEPf
Content-Type: application/json

{
  "ssoProtection": {
    "deploymentType": "all"
  }
}
```

The equivalent authenticated Vercel CLI/API invocation may be used, but the resulting project setting must be verified rather than assumed.

The barrier is considered active only when both checks pass:

1. an anonymous request to the Production domain is blocked by Vercel Authentication;
2. an authenticated operator request still reaches PartGraph, for example:

```bash
vercel curl /api/v1/health/ready --deployment <production-deployment-url>
```

Do not begin the Production database migration before both checks pass.

### Restoring normal access

After the candidate is promoted and verified while protection is still active, restore the **exact protection configuration captured before cutover**.

Do not blindly set `ssoProtection=null`. PartGraph already uses protected Preview deployments, so blindly disabling protection could weaken the existing Preview security posture.

After restoration, verify:

- the Production domain is public again;
- Preview protection still behaves as it did before cutover;
- the Production `/api/v1/health/ready` endpoint is healthy;
- no unexpected runtime errors appeared during reopening.

### Fallback: dedicated maintenance deployment

A dedicated maintenance deployment remains the fallback only if the selected Vercel Authentication control cannot be activated or verified at the cutover. It must be separately approved before use and must have no PartGraph database mutation path.

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
