# PartGraph MVP Roadmap

Status: **Implementation through Phase 9 is validated; repository hygiene/remediation is complete and Phase 10 non-production preparation is in progress.**  
Architecture authority: `docs/BLUEPRINT.md`  
Audit/deferred-work register: `docs/AUDIT_STATUS.md`

## Working rules

- Application code stays generic. Real vehicle identity and mechanical facts belong in approved data/evidence, not make/model/year/trim branches.
- Missing or conflicting automotive truth remains missing/conflicting until reviewed.
- External providers and AI may create candidate information only; they do not directly publish canonical truth.
- Owner Garage, repair-session, inventory, observation, and media state remains private.
- Unsupported computer/service-tool work cannot be represented as completed physical repair work.
- Production changes, PR #84 merge, production migration, and provider activation require separate explicit authorization. Phase 10 non-production preparation/build work is authorized; that authorization does not permit Production mutation or PR #84 merge.
- Historical migrations and the artifacts they import remain immutable/reconstructable even when their current data lineage has been retired.

## Current boundary

Repository hygiene, coding-agent hallucination review, and decision-free remediation are complete at the current branch boundary. Development may proceed with bounded Phase 10 non-production preparation while Production mutation and PR #84 merge remain separately gated.

The active implementation line is `partgraph-mvp-consolidation`; PR #84 remains draft/unmerged. Production remains intentionally separate, including the production database at migration `0020_catalog_coverage`.

## Phase status

| Phase | Status | Remaining boundary |
| --- | --- | --- |
| 0 — Repository consolidation | Functionally complete | Final merge to `main` remains part of the production-safe cutover sequence. |
| 1 — Behavioral correctness | Complete for MVP | Hosted durable private-photo persistence was proven in Vercel Preview. |
| 2 — Resilience | Complete for current read-only offline MVP | Offline writes/journaling/reconciliation remain out of current scope. |
| 3 — Security and RBAC | Complete for current operations | Production infrastructure/governance items remain separately gated. |
| 4 — Canonical schema | Complete | The MVP can represent all planned canonical/private domains without vehicle-specific application logic. |
| 5 — Migration baseline | Complete | Fixed adopted baseline remains `0046_pipeline_actor_roles`; production is not reset or auto-advanced. |
| 6 — Canonical data/provider pipeline | In progress | Live deployed NHTSA operator HTTP proof and broad repair-knowledge population remain unfinished. |
| 7 — Primary deep vehicle | Complete | 2009 Honda Civic Hybrid deep workflow proof is data/evidence-driven. |
| 8 — Five-model reference fleet | Complete | Civic, Camry, F-150, Forester, and Tucson execute through shared generic runtime paths. |
| 9 — Final MVP validation | Complete | All 18 final validation layers passed, including hosted durable-photo persistence. |
| 10 — Production cutover | Preparation in progress | Real Production-copy migration/restore, rollback behavior, fail-closed preflight, and safe cutover choreography are machine-checked. Current preflight remains NO-GO because Production backup/protection, selection/proof of the traffic barrier, and explicit Production authorization remain unresolved; other BLOCKED governance/observability findings are surfaced for final disposition. |

## Phase 6 remaining work

Only two substantive non-production roadmap items remain open:

1. **Live NHTSA HTTP ingestion proof.** The existing operator endpoint and governance path must be exercised against a deployed non-production environment using an authorized operator session. Configuration or fixture-based tests alone do not count.
2. **Broad canonical repair knowledge.** The reviewed reference corpus proves the architecture but is not broad automotive coverage.

The previously added credential-dependent hosted-NHTSA proof scaffold was removed during repository hygiene because it could not execute in the current environment and duplicated existing operator/NHTSA contract coverage. Reintroduce a hosted proof only when the required authorized non-production operator execution path actually exists.

## Phase 9 validation contract

The permanent final suite covers:

- unit/domain contracts
- API contracts
- authentication/security
- RLS and owner isolation
- migrations and production-copy migration
- full-stack and verified-guidance integration
- real browser E2E
- randomized and reference-fleet acceptance
- offline/degraded behavior
- timeout/ambiguous-write recovery
- downstream-operation semantics
- unsupported computer/service-tool boundaries
- durable photo persistence
- data-free executable source
- RBAC authorization

Phase 9 completion was proven on clean implementation head `5a95001b594e14437492dd131d41f519619a0eff` with MVP Final Validation CI #205 at 18/18 and a READY Vercel Preview. Subsequent audit/remediation heads also retained the permanent validation gates.

## Phase 10 preparation

The first Phase 10 implementation slice is `.github/workflows/production-copy-rehearsal.yml`. It is manual-only and creates a fresh expiring Neon child of the stable `production` branch. The job fingerprints copied owner/private state at the current Production baseline `0020_catalog_coverage`, migrates only that child to repository head, verifies the copied baseline rows and columns remain unchanged, and runs the migrated-database schema contracts.

The workflow deliberately does not seed synthetic owner state into the copy, does not accept a Production database URL, and does not deploy application code or publish canonical automotive data. It requires the repository `NEON_API_KEY` secret when dispatched.

Real production-copy migration evidence already exists independently of that automation. Neon branch `phase9-production-copy-validation-2026-09-17` (`br-shiny-sunset-aebi1qvo`) is a direct child of `production` (`br-shiny-silence-aexgk2zm`), created from the Production point-in-time `2026-09-17T23:19:04Z`. On 2026-09-20, Production was reverified at `0020_catalog_coverage` while the isolated copy was at `0063_photo_storage_outbox`. A read-only baseline-column comparison succeeded for all 18 owner/private tables: all 35 persisted baseline rows had matching row counts and deterministic row digests, with no missing baseline column encountered.

This evidence satisfies the real isolated-copy preservation proof. The staged GitHub workflow has not been dispatched because GitHub requires a `workflow_dispatch` workflow to exist on the default branch, while PR #84 remains intentionally unmerged. Its first dispatch is therefore a later repeatability check, not a pre-merge cutover prerequisite.

A 2026-09-20 isolated snapshot restore drill also passed with all 18 baseline owner/private tables and 35 persisted rows matching Production. Restore mechanics are therefore proven. Production backup freshness remains blocked because no automatic snapshot schedule is configured and current project history retention is 6 hours.

Fresh non-production capability probes show that the current `free_v3` project cannot close that gate by configuration alone: automatic snapshot scheduling is disabled for the project, and branch protection is rejected by the current-plan limit despite zero protected branches being present. This state is versioned in `ops/cutover/phase10_backup_capability_v1.json`. REL-001 is therefore waiting on a provider-plan/capability decision or an explicitly approved equivalent backup/protection design, not more decision-free application development.

Rollback compatibility is now explicit and machine-checked. The migrated schema preserves all 36 Production baseline tables and all 320 baseline columns, but `0063_photo_storage_outbox` makes `repair_photo_evidence.storage_state` required without a server default. The currently deployed Production photo-write path does not supply that field, so application-only rollback after schema promotion is prohibited. Rollback must be a forward correction or coordinated database restore plus prior application deployment.

The Phase 10 operator preflight is now versioned in `ops/cutover/phase10_preflight_v1.json` and `docs/PRODUCTION_CUTOVER_PREFLIGHT.md`, with a permanent CI contract test. The current assessment is intentionally **NO-GO**. In addition to PG-AUD-REL-001 and explicit Production authorization, the preflight treats PG-AUD-DEP-005 as a hard cutover-order gate because the current Production Vercel deployment was produced from documentation-only `main` commit `d68606162c725348779e2d4f93e8819eb8469f21`. REL-007 and DEP-003 remain visible as blocked findings that require explicit final disposition rather than being silently ignored.

The DEP-005 sequence is now prepared in `ops/cutover/phase10_cutover_choreography_v1.json`. The candidate is staged as a Production-target Vercel deployment without domain assignment, public traffic is blocked by an explicitly approved/proven barrier, the database is migrated and verified, the candidate is tested directly, and only then is Production traffic promoted/reopened. No traffic barrier is selected yet and normal Git deployment behavior has not been changed, so DEP-005 remains BLOCKED rather than being marked complete prematurely.

REL-007 has also been reduced to an external capability decision. PartGraph's telemetry, SLO catalog, structured events, correlation IDs, and incident procedures are implemented. The current Vercel Hobby setup has runtime-log visibility but no active alert-delivery backend; Drains require an eligible paid Vercel plan and no external backend is configured. The boundary is versioned in `ops/observability/alert_delivery_capability_v1.json`. No additional decision-free application instrumentation is required to close the engineering portion of this finding.
## Production safeguards

Production cutover is not implied by completed MVP validation or by authorization to perform Phase 10 non-production preparation. Before any Production mutation:

- select one exact green source commit;
- retain the proven snapshot-restore path, and separately approve/configure Production backup freshness/retention before cutover;
- deploy frontend/backend from the same source;
- apply only explicitly approved, rehearsed migrations;
- verify health/readiness and real owner state;
- run production-safe smoke checks;
- do not seed unreviewed automotive data as canonical truth.

## Deferred work

Items that are intentionally blocked, future-scale controls, or post-MVP hardening are tracked in `docs/AUDIT_STATUS.md`. Do not convert them into implementation work merely to reduce the count.

Historical progress narratives and superseded audit working notes remain recoverable from Git history rather than being kept in the active tree.
