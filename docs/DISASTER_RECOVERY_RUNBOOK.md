# PartGraph Production Disaster Recovery Runbook

Status: active remediation control for `PG-AUD-REL-001`.

## Scope

This runbook covers the production PostgreSQL database in the PartGraph Neon project. It does not authorize production schema migration, PR #84 merge, provider activation, branch deletion, or canonical-data publication.

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
5. Recovery is always restored to a disposable recovery branch first. Never overwrite production as the first recovery action.
6. Verify schema revision and owner/repair state on the recovery branch before any traffic or connection-string change.
7. Recovery branches/snapshots are not deleted automatically by this runbook; cleanup requires the normal explicit authorization for destructive infrastructure actions.

## 2026-09-16 restore drill

Source branch: `production` (`br-wild-silence-aet2bzfe`).

A manual snapshot was created:

- snapshot: `snap-solitary-snow-aegiq03s`
- name: `partgraph-production-dr-audit-2026-09-16`
- expiry: 2026-09-23

The snapshot was restored to a separate recovery branch:

- recovery branch: `recovery-drill-2026-09-16`
- branch id: `br-shiny-silence-aexgk2zm`

Read-only verification on both production and the restored recovery branch returned the same critical baseline:

- Alembic revision: `0020_catalog_coverage`
- `user_vehicles`: 4
- `repair_sessions`: 2

This proves that a production snapshot can currently be restored to an isolated branch and that the sampled owner/repair state survives the restore.

## Current plan limitations discovered during remediation

The PartGraph Neon project currently reports `history_retention_seconds = 21600` (six hours).

Attempting to protect the production branch failed because the current Neon plan has no remaining protected-branch capacity. The API returned: `You have reached the maximum number of protected branches for your current plan.` The project currently shows no protected branch, so the effective free-plan allowance appears insufficient for this control.

Attempting to configure a daily seven-day snapshot schedule also failed because backup-schedule creation is not enabled for this project.

Therefore `PG-AUD-REL-001` is not complete. The restore-drill portion is proven, but production branch protection, automatic backup scheduling, and longer point-in-time retention remain blocked by current Neon plan capabilities.

## Cutover gate

Before PR #84 can be considered production-safe, re-check the Neon plan and require all of the following:

- production branch protection enabled;
- automatic daily snapshot/backup protection enabled with at least seven-day retention;
- point-in-time/history retention increased from six hours to at least seven days, or an explicitly approved equivalent backup strategy is in place;
- a recent recovery drill exists and its verification matches production owner/repair state;
- backup/retention status is included in the production cutover checklist.

If the selected Neon plan cannot provide these controls, production cutover remains blocked until an equivalent durable backup and recovery mechanism is explicitly designed and approved.
