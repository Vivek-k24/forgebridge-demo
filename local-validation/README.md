# PartGraph local acceptance harness

This directory is a **local-only black-box/integration acceptance block**. It is intentionally separate from `api/tests`, GitHub Actions, production Docker images, and deployment workflows.

## What it proves

The default run executes **20 seeded-random use cases**. Each case is assigned a vehicle from a synthetic pool spanning the supported PartGraph manufacturer policy, random model year/market/model/trim/configuration data, and a synthetic repair category. The 20 scenario contracts collectively exercise:

- registration/authentication
- manual exact vehicle identity
- RepairSession creation
- edit lease ownership and takeover
- pause/resume/archive
- storage locations and fastener memory
- manual procurement inventory
- observations and private photo round-trip
- exact RepairDefinition binding
- verified requirement/readiness manifest
- ordered -> have readiness transitions
- reusable Garage carry-forward
- deterministic verified guidance
- Inventory action blockers
- procedure completion, block/recovery, permitted skip, rejected unsafe skip
- Resume/current-action consistency
- append-only event history
- idempotent replay and conflict rejection
- cross-user isolation
- version-pinned superseded definition reconstruction
- professional-required and prohibited capability boundaries
- unbound -> bound workflow

A run fails if any selected use case fails **or** if any registered workflow contract was not actually exercised.

## Vehicle breadth

`vehicle_pool.json` currently contains 62 explicitly synthetic fixtures covering all 31 makes in the PartGraph supported/legacy brand policy. The ordinary 20-case run intentionally chooses 20 different makes before it repeats a make. `-AllBrands` chooses one randomized vehicle for every supported/legacy make (31 cases with the current policy).

The vehicle names are realistic fixture data, but this file is **not a fitment or repair authority**. The repair definitions, parts, tools, fluids, hardware, warnings, and instructions inserted by the harness are intentionally synthetic and are visibly marked as local acceptance fixtures.

## Isolation

The harness creates its own Compose project:

- PostgreSQL database: `partgraph_acceptance`
- disposable PostgreSQL volume
- disposable private-media volume
- isolated FastAPI container exposed at `http://localhost:18000`
- one-shot acceptance runner container

The PowerShell script starts by deleting the previous **acceptance** volume and normally deletes it again when the run finishes. It does not use the normal `partgraph` Compose volume.

Do not change `compose.acceptance.yaml` to point at your normal PartGraph database.

## Why the repair data is synthetic

This harness tests software behavior, not mechanical truth. Random web data would make the suite non-repeatable and could blur PartGraph's canonical source-authority boundary. The local fixtures therefore create complete deterministic requirements/procedures solely inside the disposable acceptance database.

No external repair source is collected, promoted, or treated as production truth by this harness.

## Future workflow rule

When a new PartGraph user workflow is added, extend this local block in the same implementation cycle:

1. add the workflow name to `WORKFLOW_CONTRACTS`;
2. add or extend an acceptance scenario that produces an observable result for it;
3. mark the contract covered only after that result was actually asserted;
4. keep the harness outside CI/CD unless the project explicitly changes that policy later.

This makes the local acceptance report a growing product contract instead of a one-time Block 11 script.
