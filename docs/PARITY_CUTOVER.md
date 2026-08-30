# PartGraph Five-PR Parity Cutover

This document records the final ownership and compatibility state after the bounded five-PR architecture restructuring tracked by issue #62.

## Canonical runtime ownership

The FastAPI composition root now mounts the implemented product through these canonical boundaries:

- `partgraph.identity`
  - authentication/session/CSRF owner boundary
  - canonical `VehicleConfiguration` taxonomy and selection
  - private `UserVehicle` and VIN protection/resolution
- `partgraph.knowledge`
  - catalog staging and source governance
  - `MechanicalClaim`
  - repair definitions, requirements, evidence, procedures, dependencies, and capability policy
- `partgraph.repair_experience`
  - `RepairSession`, immutable events, projections, leases, and resume
  - readiness/Garage reconciliation
  - verified procedure progress/guidance
  - repair memory, observations, photos, and reorientation
- `partgraph.intelligence`
  - provider-neutral intelligence contracts
  - private AI invocation audit ownership
- `partgraph.assistance`
  - existing deterministic owner-facing explanation endpoint
  - consumes canonical Identity/Repair Experience state and does not create mechanical truth

`partgraph.main` and `partgraph.orm_registry` are the authoritative composition/bootstrap points.

## Compatibility policy

Pre-restructure packages such as `partgraph.auth`, `partgraph.vehicle`, `partgraph.user_vehicle`, `partgraph.catalog`, `partgraph.repair_definition`, `partgraph.repair_session`, and `partgraph.repair_memory` remain only where they still provide a tested compatibility surface for existing code/tests.

They are not the application composition path and they do not own duplicate SQLAlchemy models or persisted tables. New PartGraph runtime code should import canonical domain packages directly.

Compatibility shims may be removed later only as a normal breaking-change decision with explicit migration/release handling. They are not required to be deleted merely to make the repository look cleaner.

## Persisted-state invariants

The restructuring does not reset or replace persisted data. Existing table names, identifiers, foreign keys, row-level security policies, encrypted VIN fields, repair-session history, projection state, readiness/procedure progress, repair memory, and AI audit rows remain governed by the existing Alembic lineage through migration `0014_ai_invocation_audit`.

Forward migration compatibility and downgrade/re-apply checks remain part of API CI. A persistent legacy revision must continue to upgrade without requiring a PostgreSQL volume reset.

## Behavioral parity contract

The required supported journey remains:

`register -> identify/save vehicle -> create RepairSession -> bind exact verified repair -> reconcile readiness -> follow verified procedure -> record progress/exceptions/evidence -> pause/resume -> complete/archive`

The restructuring must also preserve:

- exact `VehicleConfiguration` applicability;
- canonical mechanical truth separate from private owner state;
- provenance, review, and conflict boundaries;
- prohibited/professional-required capability fail-closed behavior;
- cross-user row-level security and insecure direct object reference (IDOR) isolation;
- VIN privacy and encryption rules;
- append-only repair-session history;
- lease and idempotency behavior;
- deterministic repair operation when AI is disabled or unavailable;
- existing GitHub Actions, GitHub Container Registry (GHCR), GitHub Pages, Compose, and local-only acceptance behavior.

## Final regression guard

`api/tests/test_parity_cutover.py` asserts that the running application uses canonical routers and that deterministic assistance/private repair-memory authentication resolve to canonical domain objects. Existing boundary tests continue proving compatibility shims re-export the same ORM classes rather than duplicating tables.

No future roadmap capability is claimed by this cutover. Real source collection, autonomous agents, external model invocation, embeddings/vector search, model training, mechanical topology expansion, and new production hosting remain separate future work.
