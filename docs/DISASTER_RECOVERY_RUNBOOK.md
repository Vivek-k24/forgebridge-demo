# PartGraph Production Disaster Recovery Runbook

Status: active remediation control for `PG-AUD-REL-001`.

## Scope

This runbook covers the production PostgreSQL database in the PartGraph Neon project. It does not authorize production schema migration, PR #84 merge, provider activation, branch deletion, canonical-data publication, or a change to Production backup policy.

## Recovery objectives

For the MVP production database, use these initial recovery objectives until real production traffic and contractual requirements justify tighter values:

- Recovery point objective (RPO): 24 hours maximum for scheduled backup protection; point-in-time history should be longer than the current six-hour project setting when the Neon plan permits it.
- Recovery time objective (RTO): 4 hours from confirmed database-loss incident to a verified recovery target ready for controlled application reconnection.

These are operational targets, not a claim that the current Neon plan already satisfies them.

## Required production controls

1. The production Neon branch must be protected against accidental destructive branch operations.
2. Automatic production snapshots/backups must run at least daily with at least seven days of retention.
3. Neon point-in-time/history retention should be at least seven days when the project plan supports it.
4. A restore drill must be performed after material database/storage changes and at least before production cutover.
5. Recovery is always restored to a disposable recovery branch first. Never overwrite Production as the first recovery action.
6. Verify schema revision and owner/repair state on the recovery branch before any traffic or connection-string change.
7. Recovery branches/snapshots are not deleted automatically by this runbook; cleanup requires the normal explicit authorization for destructive infrastructure actions.

## Current verified Neon topology — 2026-09-20

Read-only inspection of the connected PartGraph Neon project (`empty-mouse-99596302`) established:

- current Production: `production` (`br-shiny-silence-aexgk2zm`);
- Production is both the primary and default branch;
- Production Alembic revision: `0020_catalog_coverage`;
- Production branch protection: disabled;
- automatic Production snapshot schedule: none;
- project point-in-time history retention: `21600` seconds (6 hours);
- connected project subscription reports `free_v3`;
- current manual DR snapshot: `partgraph-production-dr-audit-2026-09-16` (`snap-solitary-snow-aegiq03s`), expiring 2026-09-23.

These values are observations, not authorization to change Production settings.

## Historical 2026-09-16 restore event

The September 16 snapshot/restore occurred while the branch identities were transitioning. Git/Neon IDs, not mutable branch names, are the durable audit reference.

The manual snapshot was created from branch object `br-wild-silence-aet2bzfe`:

- snapshot: `snap-solitary-snow-aegiq03s`;
- name: `partgraph-production-dr-audit-2026-09-16`;
- expiry: 2026-09-23.

The restore produced branch object `br-shiny-silence-aexgk2zm`. That branch object is now the current primary/default `production` branch. The former source object `br-wild-silence-aet2bzfe` remains non-production and is currently named `recovery-drill-2026-09-16`.

The earlier runbook wording treated those names as stable identities. That was misleading after restore finalization renamed/reassigned branch labels. This section preserves the historical object IDs while the current topology section above is authoritative for present operations.

## 2026-09-20 isolated restore drill

The existing manual snapshot `snap-solitary-snow-aegiq03s` was restored again to a new isolated branch without changing the Production primary/default assignment.

Recovery target:

- branch: `phase10-dr-restore-drill-2026-09-20`;
- branch id: `br-icy-leaf-ae522322`;
- restore status: finalized;
- automatic expiry: `2026-09-21T14:00:00Z`;
- Alembic revision: `0020_catalog_coverage`;
- public tables: 36.

Read-only recovery verification matched current Production on:

- users: 4;
- Garage vehicles: 4;
- repair sessions: 2;
- repair-session events: 9.

The complete baseline owner/private preservation check selected the exact Production-`0020` columns for all 18 owner/private tables. All 18 tables matched Production on row count and deterministic row digest, covering 35 persisted rows with zero differences.

Production remained `br-shiny-silence-aexgk2zm`, primary/default, and at `0020_catalog_coverage` throughout the drill.

This proves the current snapshot restore mechanism and representative owner/repair recovery path. It does not prove that backup freshness or retention meets the target RPO.

## Current backup-policy limitation

`PG-AUD-REL-001` remains blocked on Production backup policy, not restore mechanics.

Current read-only evidence shows:

- no automatic snapshot schedule on Production;
- only six hours of project point-in-time history retention;
- Production branch protection disabled.

Fresh non-production capability probes on 2026-09-20 made the limitation explicit:

- requesting a daily automatic snapshot schedule with seven-day retention on temporary child branch `br-muddy-butterfly-aebaici0` failed with Neon reporting that backup schedule creation is not enabled for this project;
- requesting branch protection on non-production branch `br-shiny-sunset-aebi1qvo` failed because the current plan's protected-branch limit was reached;
- an account-wide read confirmed there are currently zero protected branches, so that rejection is not caused by another branch consuming the quota;
- both probes left Production unchanged.

The machine-readable evidence is `ops/cutover/phase10_backup_capability_v1.json`.

This means REL-001 is currently an infrastructure capability/policy blocker, not unfinished repository code. Re-test only after the Neon plan/capabilities change or an equivalent durable backup design is explicitly approved.

Do not change Production snapshot schedules, retention, or branch protection merely to clear the finding. Those are Production infrastructure decisions and require separate authorization.

## Cutover gate

Before PR #84 can be considered production-safe, require all of the following:

- Production branch protection enabled, or an explicitly approved equivalent destructive-operation control;
- automatic daily snapshot/backup protection with at least seven-day retention, or an explicitly approved equivalent durable backup strategy;
- point-in-time/history retention increased from six hours to at least seven days, or covered by that approved equivalent strategy;
- a recent recovery drill with verified owner/repair state;
- backup/retention status recorded in the production cutover checklist.

The restore-drill condition is currently proven. Backup freshness/protection remains unresolved, so Production cutover remains blocked on this gate.
