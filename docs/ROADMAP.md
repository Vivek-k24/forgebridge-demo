# PartGraph MVP Roadmap

Status: **Implementation through Phase 9 is validated; repository hygiene/remediation is complete and Phase 10 non-production preparation is authorized.**  
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
| 10 — Production cutover | Preparation started | Non-production preparation is authorized. Production cutover still requires separate Production authorization plus DR/rollback/environment readiness. |

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

## Production safeguards

Production cutover is not implied by completed MVP validation or by authorization to perform Phase 10 non-production preparation. Before any Production mutation:

- select one exact green source commit;
- verify production backup/restore and rollback readiness;
- deploy frontend/backend from the same source;
- apply only explicitly approved, rehearsed migrations;
- verify health/readiness and real owner state;
- run production-safe smoke checks;
- do not seed unreviewed automotive data as canonical truth.

## Deferred work

Items that are intentionally blocked, future-scale controls, or post-MVP hardening are tracked in `docs/AUDIT_STATUS.md`. Do not convert them into implementation work merely to reduce the count.

Historical progress narratives and superseded audit working notes remain recoverable from Git history rather than being kept in the active tree.
