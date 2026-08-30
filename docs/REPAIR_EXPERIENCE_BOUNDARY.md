# Repair Experience Boundary

Restructure PR 3/5 makes `partgraph.repair_experience` the owner of private, owner-scoped repair state and the behavior that mutates or projects that state.

## Owned state

- `RepairSession`
- immutable `RepairSessionEvent`
- rebuildable `RepairSessionProjection`
- `RepairProcedureActionState`
- `UserGarageInventoryItem`
- `RepairRequirementState`
- repair storage locations and exceptional hardware memory
- per-session inventory memory
- user observations
- private repair photo evidence

## Owned behavior

The existing session lifecycle, lease/idempotency handling, readiness reconciliation, version-pinned definition binding, guided progress, Resume/reorientation, repair-memory mutations, observations, photo handling, and projection rebuild behavior are preserved.

This PR changes Python ownership, not database truth. Existing table names, foreign keys, row-level security policies, event immutability, API paths, IDs, persisted histories, and repair-definition version pins remain unchanged.

## Canonical boundary

`partgraph.knowledge` remains the source of verified repair definitions, requirements, procedures, evidence, and capability policy. Repair Experience may bind to and record progress against version-pinned Knowledge objects but may not redefine canonical mechanical truth.

## Compatibility

The pre-restructure `repair_session`, `repair_memory`, and private readiness imports remain temporary compatibility bridges. They resolve to the same Repair Experience model and service objects rather than defining parallel state. PR 5/5 may remove those bridges after parity cutover is proven.

The relocated memory package retains a small internal compatibility surface for its historical relative imports. It is intentionally local to Repair Experience and introduces no new application capability or persistence layer.

## Deferred work

No collection adapters, autonomous agents, external model calls, embeddings, training, or new repair capability are introduced here.
