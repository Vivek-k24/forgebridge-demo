# PartGraph local acceptance harness

This directory is a **local-only black-box/integration acceptance block**. It is intentionally separate from `api/tests`, GitHub Actions, production Docker images, and deployment workflows.

## What it proves

A normal run has two layers.

### Platform probes

Before the random repair cases, `platform_acceptance.py` exercises the product boundaries that are not naturally repeated in every repair session:

- API/database readiness
- supported/legacy manufacturer policy
- vehicle selector normalization and excluded-brand rejection
- register, session-cookie authentication, `/auth/me`, logout, and login
- account unit preferences
- VIN syntax/check digit
- VIN provider adapter using a **local vPIC-compatible stub**, not the Internet
- VIN owner cache
- encrypted VIN save/masking and duplicate protection
- UserVehicle archive/list behavior

### Cross-manufacturer repair cases

The default run executes **20 seeded-random use cases**. Each case is assigned a vehicle from the synthetic pool, a repair template, and one focused scenario. Every case also executes the common repair-continuity path.

The 20 scenario contracts collectively exercise:

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

`vehicle_pool.json` currently contains **62 explicitly synthetic vehicle fixtures covering all 31 makes** in the current PartGraph supported/legacy brand policy. The ordinary 20-case run intentionally chooses 20 different makes before it repeats a make. `-AllBrands` chooses one randomized vehicle for every supported/legacy make (31 cases with the current policy).

Twenty cases cannot literally cover every real model and trim. The purpose is broad cross-manufacturer architecture validation. Increase the fixture pool over time as new vehicle-shape edge cases matter.

Before the black-box repair tests begin, `seed_vehicle_pool.py` inserts these vehicle configurations into the disposable canonical vehicle table. The public manual-vehicle requests must then resolve back to those exact rows; the acceptance runner does not bypass the public vehicle workflow.

The names are realistic fixture data, but the pool is **not a fitment or repair authority**. The repair definitions, parts, tools, fluids, hardware, warnings, and instructions inserted by the harness are intentionally synthetic and visibly marked as local acceptance fixtures.

## Isolation

The harness creates its own Compose project:

- PostgreSQL database: `partgraph_acceptance`
- disposable PostgreSQL volume
- disposable private-media volume
- local VIN-provider stub
- isolated FastAPI container exposed at `http://localhost:18000`
- one-shot acceptance runner container

The PowerShell script starts by deleting the previous **acceptance** volume and normally deletes it again when the run finishes. It does not use the normal `partgraph` Compose volume.

Do not change `compose.acceptance.yaml` to point at your normal PartGraph database.

## Why the repair data is synthetic

This harness tests software behavior, not mechanical truth. Random web repair data would make the suite non-repeatable and could blur PartGraph's canonical source-authority boundary. The local fixtures therefore create complete deterministic requirements/procedures solely inside the disposable acceptance database.

No external repair source is collected, promoted, or treated as production truth by this harness. The VIN integration uses a local protocol-compatible stub so the harness does not depend on network availability.

## PowerShell

From the repository root:

```powershell
.\local-validation\run.ps1
```

Different reproducible assignment of vehicles/scenarios:

```powershell
.\local-validation\run.ps1 -Seed 314159
```

One randomized vehicle from every currently supported/legacy make:

```powershell
.\local-validation\run.ps1 -AllBrands -Seed 314159
```

Keep the disposable stack after the run for API/SQL inspection:

```powershell
.\local-validation\run.ps1 -Seed 314159 -Keep
```

Enable Python traceback details for a failing case:

```powershell
$env:PARTGRAPH_ACCEPTANCE_TRACEBACK = "true"
.\local-validation\run.ps1 -Seed 314159 -Keep
Remove-Item Env:PARTGRAPH_ACCEPTANCE_TRACEBACK
```

A successful run ends with both:

```text
RESULT: PASS — all selected cases and workflow contracts passed.
PASS: PartGraph local acceptance harness completed successfully.
```

and PowerShell `$LASTEXITCODE` is `0`.

## Inspection after `-Keep`

Swagger/API:

```powershell
Start-Process http://localhost:18000/docs
```

PostgreSQL:

```powershell
docker compose -p partgraph-acceptance -f .\local-validation\compose.acceptance.yaml exec postgres `
  psql -U partgraph -d partgraph_acceptance
```

Useful SQL:

```sql
SELECT count(*) FROM repair_sessions;
SELECT event_type, count(*) FROM repair_session_events GROUP BY event_type ORDER BY event_type;
SELECT progress_state, count(*) FROM repair_procedure_action_states GROUP BY progress_state;
SELECT readiness_state, count(*) FROM repair_requirement_states GROUP BY readiness_state;
SELECT count(*) FROM user_garage_inventory_items;
```

Cleanup after inspection:

```powershell
docker compose -p partgraph-acceptance -f .\local-validation\compose.acceptance.yaml down -v --remove-orphans
```

## Future workflow rule

When a new PartGraph user workflow is added, extend this local block in the same implementation cycle:

1. add the workflow name to `WORKFLOW_CONTRACTS` or the platform-probe registry;
2. add or extend an acceptance scenario that produces an observable result for it;
3. mark the contract covered only after that result was actually asserted;
4. keep the harness outside CI/CD unless the project explicitly changes that policy later.

This makes the local acceptance report a growing product contract instead of a one-time Block 11 script.
