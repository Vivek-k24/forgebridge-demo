# PartGraph local catalog workbench

The catalog workbench is an operator-controlled research runtime for gathering and reconciling vehicle-configuration evidence on local compute. It is intentionally separate from the interactive repair path and does not require Vercel or Neon.

## First batch

The first workbench batch is the 363 candidate rows imported from `Selected_Asian_Brands_1996_2000.xlsx`:

- Acura: 62
- Honda: 114
- Lexus: 18
- Subaru: 63
- Toyota: 106

These are **seed candidates**, not a complete 1996-2000 vehicle universe and not automatically verified truth.

Dashboard terms:

- **Candidates**: rows currently in the declared batch.
- **Collected**: candidates for which a source-collection pass completed. A completed pass can still contain source failures or insufficient evidence.
- **Verified**: candidates for which at least three independent sources support the exact configuration signature used for canonical identity.
- **Conflict/unresolved**: evidence is insufficient or contradictory; the workbench does not force a canonical result.

The first batch completes research for these 363 rows. Broader missing-model/year/trim discovery belongs in later batches with their own explicit scopes.

## Corroboration rule

For ordinary vehicle configuration identity:

1. Start with up to five independent sources.
2. A reachable page is not a verification vote by itself.
3. A source contributes a configuration vote only when the fetched material supports the relevant year, make, model/alias, trim/grade, engine signature, and transmission signature.
4. Three independent configuration matches are the minimum automatic verification threshold.
5. A fourth or fifth source is retained when available and is especially useful when earlier sources fail, disagree, or are incomplete.
6. Source disagreements remain visible in the source matrix and operational log. Do not turn a timeout, 404, block, or partial match into agreement.
7. Manufacturer-only service specifications, safety-critical claims, exact repair procedures, torque values, fluid requirements, fitment, and similar mechanical facts retain their stricter domain-specific evidence boundaries. Configuration identity verification does not automatically verify those facts.

The local v1 adapters attempt:

- NHTSA vPIC
- Cars.com
- Edmunds
- Kelley Blue Book (KBB)
- MotorTrend

NHTSA model evidence can support year/make/model identity, but it does not count as an exact trim/powertrain configuration vote unless the retrieved source actually contains that scope. The worker records per-field match results rather than treating every successful HTTP request as evidence.

Do not bypass authentication, paywalls, CAPTCHA, access controls, or paid-source activation. A blocked source remains a blocked source in the log and the worker proceeds with the remaining configured references.

## Local runtime

The normal local stack is:

```text
browser
  -> local Nginx/React web :5173
  -> local FastAPI :8000
  -> local PostgreSQL :5432

local collector worker
  -> public reference sources
  -> local-data/workbench raw-response cache
  -> PostgreSQL workbench/staging/evidence tables
```

Vercel and Neon are not required for collection.

The workbench API is disabled by default in normal/cloud runtime configuration. `compose.yaml` explicitly enables it for local Docker and the local web build. The `Catalog workbench` navigation item is therefore not built into the default Vercel frontend.

## Clone and run on Windows

Requirements:

- Git
- Docker Desktop with Docker Compose v2

Clone the repository and switch to the branch containing the workbench while it is under review:

```powershell
git clone https://github.com/Vivek-k24/forgebridge-demo.git
cd forgebridge-demo
git checkout partgraph-local-catalog-workbench
```

Start everything:

```powershell
.\scripts\workbench.ps1 start
```

Then open:

```text
http://localhost:5173/#/catalog
```

Register/login through the normal PartGraph account flow if the local database does not already contain an account.

The first startup builds the images and applies Alembic migrations. Later startups reuse the existing PostgreSQL volume and source cache.

## Dashboard controls

Each make card contains collection and verification progress plus a job control:

- **Start**: create a collection pass for that make.
- **Pause**: stop after the current safe checkpoint. Already fetched source attempts remain stored.
- **Resume**: continue the same job/cursor rather than starting over.
- **Run again**: after a completed pass, create a new pass so sources can be refreshed.
- **View activity**: select the make for the lower activity console.

The activity console shows:

- actual worker events;
- current job state and processed candidate count;
- source provider;
- source URL;
- HTTP/fetch outcome;
- per-field match result;
- local cache path;
- fetch errors/blocks where applicable.

The UI polls local APIs approximately every two seconds. It does not invoke collection during page load.

## Persistence and interruption behavior

Structured state is kept in the local PostgreSQL Docker volume. Raw successful source responses are cached under:

```text
local-data/workbench/
```

`local-data/` is git-ignored.

A make job advances its cursor only after a configuration reaches a safe checkpoint. Partial source attempts for the current configuration are retained, so a resumed job can skip already-recorded attempts.

Stopping the stack does not delete data:

```powershell
.\scripts\workbench.ps1 stop
```

Never use `docker compose down -v` as routine cleanup because `-v` deliberately removes the PostgreSQL volume.

## Using more local compute

One collector worker is the default. Multiple make jobs can be processed concurrently with two worker containers:

```powershell
.\scripts\workbench.ps1 scale2
```

Start multiple makes from the dashboard. Jobs are transactionally claimed so separate workers do not intentionally process the same queued job at the same time.

Begin with one worker until source behavior is understood. More workers increase outbound request volume and do not improve source quality.

## Logs from the terminal

To watch the collector container directly:

```powershell
.\scripts\workbench.ps1 logs
```

The dashboard remains the better audit view because it shows persisted events and source rows rather than only container stdout.

## Back up the workbench

Create a local snapshot:

```powershell
.\scripts\workbench.ps1 backup
```

The backup is written under:

```text
local-data/exports/<timestamp>/
```

It contains:

- `partgraph.dump`: PostgreSQL custom-format dump;
- `workbench/`: cached raw source material;
- `repository-commit.txt`: exact code commit used for the run;
- `created-at.txt`: backup timestamp.

This is the portable handoff unit for the research runtime.

## Publishing later

Neon is a later publication/deployment target, not the collection engine. Before publishing local results:

1. finish/inspect the relevant local workbench runs;
2. preserve unresolved/conflicting rows as unresolved;
3. create a backup;
4. review the migration/current schema version;
5. restore or selectively promote the verified PostgreSQL state into the intended Neon branch/database;
6. run the normal PartGraph migration and integration checks against that target;
7. only then point a hosted API at the published database.

Do not upload `local-data/workbench` to GitHub. Raw source cache is local research material; PostgreSQL provenance records are the structured audit trail used by PartGraph.
