# PartGraph Database Migration Promotion Runbook

Status: **migration execution contract; this document does not authorize a production migration, PR merge, provider activation, publication, or cutover.**

## Purpose

PartGraph application builds and deployments must be schema-read-only. Database schema promotion is a separate, explicit operational action so a web/API build cannot mutate a database merely because it has database credentials.

This runbook defines the required boundary for preview and eventual production schema promotion. Phase 10 production execution remains blocked until the roadmap prerequisites and explicit production approval are satisfied.

## Non-negotiable boundary

- Vercel application build scripts must not execute Alembic migration commands.
- Deploying application code must not implicitly upgrade, downgrade, stamp, reset, seed, or clean a database.
- Historical deployed migrations remain immutable; corrections use forward migrations.
- Automotive canonical publication is separate from schema migration. A schema promotion must not silently publish reviewed vehicle/repair knowledge.
- Production migration is not authorized by this runbook.

The permanent repository check `api/scripts/validate_vercel_migration_boundary.py` enforces the build-side portion of this contract in API CI.

## Required inputs before any migration action

The operator must know and record:

1. the exact source commit being evaluated;
2. the target environment and database branch;
3. the database's current Alembic revision;
4. the repository's intended Alembic head;
5. the migration range between those revisions;
6. the applicable backup/restore or branch-copy capability;
7. the expected post-migration health/schema checks;
8. whether any migration in the range performs data cleanup or other irreversible transformation.

Database credentials must come from the approved environment/secret mechanism. Do not place database URLs or credentials in source control, command examples committed with real values, logs, issue text, or PR text.

## Preview/development promotion procedure

A preview/development database may be promoted only as an explicit operator action, separate from deployment:

```bash
alembic -c api/alembic.ini current
alembic -c api/alembic.ini heads
alembic -c api/alembic.ini upgrade head
alembic -c api/alembic.ini current
```

`PARTGRAPH_DATABASE_URL` must already be injected into the execution environment through the approved secret mechanism.

After migration:

- confirm the reported revision matches the intended head;
- run the repository's migration/schema/RBAC/reference-runtime checks appropriate to that environment;
- verify API readiness before relying on the environment;
- verify that no canonical automotive knowledge was published merely because the schema changed.

A preview deployment does **not** automatically run this procedure.

## Automated isolated production-copy rehearsal

Phase 10 uses `.github/workflows/production-copy-rehearsal.yml` as the manual non-production rehearsal entry point. The workflow is intentionally `workflow_dispatch` only. It creates a new copy-on-write Neon child of the stable `production` branch in the verified PartGraph project (`empty-mouse-99596302`) and gives the child a unique GitHub Actions run name plus a one-day automatic expiry.

The workflow requires the repository secret `NEON_API_KEY`. That credential is supplied only to Neon's branch-creation action, which is pinned to the immutable commit behind the stable `v6` release. Database migration commands receive only the newly created child branch connection string returned by that action.

The rehearsal sequence is:

1. create a fresh expiring Neon child of `production`;
2. fail unless Neon reports that this run created a new child branch;
3. fingerprint all baseline owner/private tables with `api/scripts/verify_production_copy_upgrade.py` while the copy is still at `0020_catalog_coverage`;
4. resolve the repository's single Alembic head and run `alembic upgrade head` against the child only;
5. verify the baseline columns, row counts, and SHA-256 row fingerprints are unchanged after migration;
6. run `api/tests/test_mvp_migrations.py` against the migrated child;
7. retain the non-sensitive fingerprint artifact and GitHub job summary as rehearsal evidence.

No synthetic persisted-history fixture is seeded into the production copy. The workflow does not receive a Production database URL, does not downgrade/reset/restore Production, and does not deploy the application or publish canonical automotive knowledge. The child expires automatically even if a job is cancelled after branch creation.

The snapshot verifier intentionally requires the current Production baseline `0020_catalog_coverage`. If Production has advanced unexpectedly, the workflow fails before executing an upgrade. Changing that baseline is a reviewed repository change, not a runtime override.

### Default-branch dispatch constraint

GitHub only accepts `workflow_dispatch` events for a workflow file that exists on the repository's default branch. While PR #84 remains unmerged, `.github/workflows/production-copy-rehearsal.yml` exists only on `partgraph-mvp-consolidation`, so its manual-dispatch control cannot be executed yet.

Do **not** merge PR #84, copy the workflow to `main`, or add an automatic Production-copy trigger merely to make this workflow runnable. The real isolated Production-copy migration/preservation evidence below already satisfies the pre-cutover rehearsal requirement. The workflow's first successful dispatch is a repeatability check after the workflow can safely exist on the default branch; it is not a prerequisite that overrides the Production cutover boundary.
## Confirmed isolated-copy rehearsal evidence

The production-copy migration requirement has a real Neon proof in addition to synthetic CI coverage:

- Production branch: `production` (`br-shiny-silence-aexgk2zm`).
- Isolated copy: `phase9-production-copy-validation-2026-09-17` (`br-shiny-sunset-aebi1qvo`).
- The isolated branch records `parent_id=br-shiny-silence-aexgk2zm` and Production point-in-time `2026-09-17T23:19:04Z`.
- On 2026-09-20, Production remained at `0020_catalog_coverage`; the isolated copy was at `0063_photo_storage_outbox`.
- The Production schema at `0020` defined 18 owner/private tables for preservation checking. Selecting those exact baseline columns on the migrated copy succeeded for every table.
- Read-only server-side comparison found identical row counts and deterministic row digests for all 18 tables, covering 35 persisted baseline rows.
- Production remained at `0020_catalog_coverage` after the verification.

This is carried-forward real-copy migration/preservation evidence. The new `production-copy-rehearsal.yml` workflow is the repeatable Phase 10 mechanism, but its first manual dispatch is deferred until the workflow safely exists on the default branch. That later repeatability check is not a pre-merge Production-cutover prerequisite and must not be used as a reason to merge PR #84 early.
## Database restore drill evidence

On 2026-09-20, the existing manual snapshot `partgraph-production-dr-audit-2026-09-16` (`snap-solitary-snow-aegiq03s`) was restored to a new non-production Neon branch and finalized without changing the primary/default Production branch.

- Restored branch: `phase10-dr-restore-drill-2026-09-20` (`br-icy-leaf-ae522322`).
- Automatic expiry: `2026-09-21T14:00:00Z`.
- Restored Alembic revision: `0020_catalog_coverage`.
- Restored public-table count: 36, matching Production.
- Representative counts matched Production: 4 users, 4 Garage vehicles, 2 repair sessions, and 9 repair-session events.
- Full baseline owner/private comparison matched across all 18 tables and all 35 persisted rows using the exact Production baseline columns; no row-count or deterministic row-digest difference was found.
- Production remained the primary/default branch at `0020_catalog_coverage` throughout the drill.

This proves the Neon restore mechanism and representative owner-state recovery path. It does **not** close the Production backup-policy gate. At the time of the drill, the Production branch had no automatic snapshot schedule and the Neon project history-retention setting was 21,600 seconds (6 hours). Changing Production backup scheduling/retention remains a separately authorized Production infrastructure decision.
## Production promotion gate

Production schema promotion remains a Phase 10 action and must not be performed until all of the following are true:

- Phase 9 final MVP validation is complete;
- the exact production candidate commit is green;
- the complete production migration range has been rehearsed against an isolated production copy/branch;
- persisted owner-state preservation checks pass on that copy;
- database protection/restore capability required by the production cutover is available and verified;
- code/schema compatibility and application rollback behavior are documented for the selected commit;
- `docs/PRODUCTION_CUTOVER_PREFLIGHT.md` has been refreshed against the exact candidate and reports GO rather than NO-GO;
- the Production deployment-order/maintenance control is explicitly approved so schema and application cannot advance in an unsafe order;
- an operator has recorded the before/after revisions and verification plan;
- the project owner has explicitly authorized production migration/cutover.

Only after those gates are satisfied may the same explicit Alembic promotion command be run against the authorized production target. Application deployment itself remains schema-read-only.

## Verified rollback compatibility boundary

The machine-readable rollback record is `ops/cutover/phase10_rollback_v1.json`. It captures the observed Production application/database boundary and is validated by `api/tests/test_phase10_rollback_contract.py`.

Read-only comparison of Production `0020_catalog_coverage` with the real migrated Production copy at `0063_photo_storage_outbox` found:

- all 36 baseline tables still exist;
- all 320 baseline columns still exist with unchanged type/nullability/size characteristics;
- no baseline column was removed or changed;
- the old `partgraph_app` privilege narrowing on `users` does not remove the deployed application's required password-rehash update;
- one application-write incompatibility is decisive: `repair_photo_evidence.storage_state` is required at `0063`, has no database server default, and the currently deployed Production photo-create code does not supply it.

That incompatibility is intentional. Migration `0063` introduced the durable photo-storage outbox and requires an explicit state consistent with the durable payload/tombstone state. Adding a generic database default merely to preserve old-code photo inserts would bypass the outbox contract and is not an acceptable rollback strategy.

Therefore **code-only rollback to the currently deployed Production application is not safe after the Production schema reaches `0063_photo_storage_outbox` or later**. After schema promotion, rollback must use one of these coordinated paths:

1. keep the migrated schema and deploy a reviewed forward corrective application/schema change; or
2. restore the approved pre-migration database snapshot/branch and reconnect the prior application deployment as one coordinated rollback.

Do not automatically run Alembic downgrade, and do not point the old Production application at the migrated schema merely because health/read-only requests appear compatible.

## Rollback and failure handling

Do not automatically issue `alembic downgrade` after a failed or partially completed production migration.

Use this decision order:

1. **If migration did not begin:** leave the database unchanged and resolve the precondition failure.
2. **If Alembic failed transactionally and the database revision/state is unchanged:** keep application deployment/cutover paused, diagnose, and rerun only after the cause is understood.
3. **If schema advanced successfully but application deployment must be rolled back:** first determine whether the prior application version is forward-compatible with the new schema. Roll back application code only when that compatibility is proven.
4. **If a schema rollback is required:** use `alembic downgrade` only when every migration in the rollback range has a reviewed/tested safe downgrade path and data preservation is proven.
5. **If migration/data transformation is not safely reversible:** prefer a forward corrective migration or the approved database restore/branch recovery procedure rather than destructive ad-hoc SQL.

Never reset production or rewrite historical migration files to simplify rollback.

## Evidence to retain for a production migration

The eventual production-cutover record must include:

- exact Git commit;
- database target/branch identifier without credentials;
- before revision;
- intended and actual after revision;
- production-copy rehearsal result;
- owner-state/schema verification result;
- readiness/smoke result;
- backup/restore proof reference;
- operator and approval record;
- rollback/forward-fix decision if anything deviated.

These records are operational evidence. They do not replace the roadmap's Phase 9/10 gates.
