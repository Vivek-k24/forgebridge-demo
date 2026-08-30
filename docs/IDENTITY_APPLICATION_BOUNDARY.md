# Identity and application boundary

Restructure PR 4/5 moves the currently implemented authentication and vehicle-identity responsibilities under `partgraph.identity` without changing persisted schemas or supported HTTP behavior.

## Ownership

`partgraph.identity.auth` owns the existing user, session, preferences, rate-limit, CSRF, cookie-session, and authenticated-owner dependencies.

`partgraph.identity.vehicle` owns canonical `VehicleConfiguration`, exact vehicle taxonomy/canonicalization, supported-year policy, selection resolution, and the existing vehicle-identity reads.

`partgraph.identity.user_vehicle` owns private `UserVehicle`, VIN protection/fingerprinting, VIN decode cache, provider decode boundary, exact/manual identity resolution, and the existing user-vehicle routes.

`partgraph.identity.actors` is a narrow application seam exposing only the already-existing authenticated-owner dependencies. It does not introduce service accounts, autonomous agents, synthetic QA actors, additional privileges, or any new authentication mode.

## Compatibility

The pre-restructure `partgraph.auth`, `partgraph.vehicle`, and `partgraph.user_vehicle` modules remain temporary compatibility bridges. They forward to the identity-owned implementations and do not define duplicate ORM classes.

PR 5/5 may remove compatibility bridges after parity cutover is proven.

## Database and privacy invariants

No Alembic migration is required. Existing user/session/vehicle tables, IDs, foreign keys, row-level security policies, VIN ciphertext/nonces/key versions/fingerprints, cache rows, and canonical vehicle-configuration IDs remain unchanged.

Full VIN values remain excluded from normal API reads and are not added to model/AI prompts by this restructuring.

## Deferred systems

This boundary creates no collector, external contributor identity, autonomous research/QA agent, synthetic actor runtime, external model call, or new deployment target. Those remain separately gated future work.
