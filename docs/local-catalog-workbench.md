# PartGraph local catalog workbench

The catalog workbench is an operator-controlled local research runtime for gathering and reconciling vehicle data. It stays outside the interactive repair path and does not require Vercel or Neon for collection.

## First batch

The first workbench batch is the 363 seed rows imported from `Selected_Asian_Brands_1996_2000.xlsx`:

- Acura: 62
- Honda: 114
- Lexus: 18
- Subaru: 63
- Toyota: 106

These are candidate configurations, not a complete 1996-2000 vehicle universe and not automatically verified truth.

Dashboard terms:

- **Candidates**: rows in the declared batch.
- **Collected**: candidates for which a source pass completed. A completed pass may still contain blocks, failures, missing fields, or conflicts.
- **Verified configuration**: every mechanical fact asserted by the seed configuration has been corroborated under the field-level evidence rules.
- **Conflict/unresolved**: evidence is insufficient or contradictory; PartGraph does not force a canonical answer.

## Field-level collection model

The workbench does not ask one webpage to reproduce an entire vehicle row. Vehicle data is assembled field by field:

```text
independent public/OEM sources
        -> immutable raw cache
        -> source-scoped field observations
        -> deterministic nomenclature/unit normalization
        -> one vote per independent source per field
        -> field reconciliation
        -> progressive technical vehicle profile
```

Examples of separate fields include:

- identity: year, make, model, generation, trim, body style, market, drivetrain;
- powertrain: displacement, cylinder count, engine architecture, aspiration, fuel/electrification, valvetrain, technologies;
- transmission: family and speed count;
- performance: horsepower and torque;
- efficiency/emissions;
- dimensions and weight;
- chassis, steering, suspension, brakes;
- wheels and tires;
- fluid/service facts;
- electrical/charging facts;
- safety hardware.

Comfort/convenience equipment such as audio, navigation, seat trim, heated seats, and similar features is outside the core technical profile.

A compound seed value such as:

```text
1.6L VTEC-E 4-Cyl (115 hp)
```

is decomposed into independent facts such as displacement, cylinders, technology, and horsepower before comparison. Transmission is also independent from trim and engine identity.

## Adaptive collection strategy

The local collector uses a **broad-first, gap-fill** strategy. It avoids both extremes: it does not issue a separate web request for every scalar specification, and it does not blindly download every configured source for every vehicle.

For each exact candidate configuration:

1. inspect already-reconciled field evidence;
2. identify unresolved core fields asserted by the seed row;
3. select broad, high-yield sources whose declared capabilities overlap those gaps;
4. extract every applicable technical fact from each retrieved response, not only the field that caused the request;
5. reconcile again after each source;
6. if core facts remain unresolved, use the gap-fill phase only with source adapters capable of contributing those fields;
7. after core applicability is proven, the same planner may enrich unresolved non-comfort technical fields already discovered by broad extraction;
8. stop asking a provider for fields it has already supplied for that configuration.

Conceptually:

```text
exact vehicle
    -> broad high-yield collection
    -> extract all useful facts
    -> field evidence matrix
         -> verified fields: stop
         -> unresolved fields: capability-aware gap fill
         -> conflicts: collect additional independent evidence
    -> reconcile again
```

Sources are tagged with capability groups such as identity, engine/powertrain, performance, transmission/drivetrain, dimensions/capacities, chassis/running gear, electrical/charging, safety, service/fluids, and parts/fitment. A source is queried only when its declared capabilities intersect the unresolved field set.

This capability model is intentionally extensible. For example, future OEM or aftermarket parts adapters can contribute `parts/fitment` and applicable engine/transmission identity without being treated as horsepower authorities. No parts-site adapter is active in the current initial registry yet.

## Corroboration and authority rules

There is **no fixed maximum number of sources**. The source adapter registry is only the currently implemented starting set. More independent adapters may be added without changing the reconciliation rule.

For ordinary vehicle facts:

1. a successful HTTP response is not evidence by itself;
2. a source contributes only fields its retrieved material actually supports within the applicable vehicle scope;
3. one provider receives at most one vote for a field, regardless of reruns or duplicate pages;
4. three independent sources agreeing on the normalized value is the normal automatic verification threshold;
5. additional sources may be collected whenever evidence is incomplete or conflicting;
6. disagreement is retained in the source matrix rather than overwritten.

Manufacturer-authoritative facts such as exact service/fluid specifications are not allowed to become canonical merely because three generic reference sites repeat them. Applicable OEM/manufacturer evidence is retained as `manufacturer_reported` unless stronger domain-specific promotion rules apply.

Configuration identity/specification corroboration never automatically verifies repair procedures, torque values, exact fitment, or other repair-domain claims that have stricter authority requirements.

## Current source adapters

The adaptive collector currently begins with:

- NHTSA vPIC;
- FuelEconomy.gov;
- Cars.com;
- Edmunds;
- Kelley Blue Book (KBB);
- MotorTrend.

This list is an implementation starting point, **not a source ceiling or an approved-source-only policy**.

NHTSA model-year evidence contributes only the identity fields actually in scope. FuelEconomy.gov can contribute powertrain, drivetrain, fuel, transmission, and EPA efficiency facts when a record can be deterministically resolved. Generic reference pages contribute only facts extracted within the applicable model/trim window.

The FuelEconomy adapter also has a conservative model-menu fallback for sources that split a PartGraph base model into source-specific variants. For example, if a direct request for `CR-V` returns no option records but the source exposes `CR-V 2WD` and `CR-V 4WD`, the collector can discover those menu names, preserve their raw labels, and compare them at the proven base-model scope while downstream engine/transmission/drivetrain scoring still distinguishes configurations. This is generic source nomenclature handling, not a hard-coded CR-V truth rule.

Blocked/authenticated/paywalled/CAPTCHA-protected sources are not bypassed. Repeated access-control responses open a local circuit breaker so the collector stops hammering that source during the process lifetime.

## Raw cache and reprocessing

Successful source responses are cached under:

```text
local-data/workbench/
```

The raw capture is not rewritten when extraction logic improves. The extractor can re-read existing cache and rebuild field observations with **zero web requests**.

After pulling an extractor/reconciler update, use:

```powershell
.\scripts\workbench.ps1 reprocess
```

The helper temporarily stops collector workers, re-extracts/reconciles cached successful captures, then restarts the collector. This preserves the original research material and avoids downloading the same pages again just because the parser changed.

The adaptive FuelEconomy model-menu fallback is a real source request, so it runs during a new collection job, not during cache-only reprocessing.

## Local runtime

```text
browser
  -> local Nginx/React web :5173
  -> local FastAPI :8000
  -> local PostgreSQL :5432

local adaptive collector worker
  -> field-gap planner
  -> source capability registry
  -> broad collection + targeted gap fill
  -> local-data/workbench raw-response cache
  -> PostgreSQL staging/evidence/profile state
```

Vercel and Neon are not collection engines. The hosted/default frontend keeps workbench navigation disabled.

## Windows commands

Start/rebuild the stack:

```powershell
.\scripts\workbench.ps1 start
```

Open:

```text
http://localhost:5173/#/catalog
```

Other helper commands:

```powershell
.\scripts\workbench.ps1 status
.\scripts\workbench.ps1 logs
.\scripts\workbench.ps1 stop
.\scripts\workbench.ps1 scale2
.\scripts\workbench.ps1 reprocess
.\scripts\workbench.ps1 backup
```

`scale2` runs two local worker containers so different queued make jobs can be transactionally claimed in parallel. More workers increase outbound request volume and do not increase source quality.

## Persistence and interruption behavior

Structured state remains in the PostgreSQL Docker volume. Source cache remains under `local-data/workbench/`, which is git-ignored.

A make job advances only after a configuration reaches a safe checkpoint. Existing source attempts are retained. Interrupted running jobs are recovered to the queue after their heartbeat becomes stale.

Do not use `docker compose down -v` as routine cleanup; `-v` intentionally deletes the PostgreSQL volume.

## Backup

Create a portable local snapshot:

```powershell
.\scripts\workbench.ps1 backup
```

The output under `local-data/exports/<timestamp>/` contains:

- `partgraph.dump` — PostgreSQL custom dump;
- `workbench/` — cached raw source material;
- `repository-commit.txt` — exact code commit used for the run;
- `created-at.txt` — timestamp.

The raw cache and database dumps do not belong in normal Git history.

## Publishing later

Neon is a later reviewed publication target. Before publishing local results:

1. finish and inspect the relevant local runs;
2. preserve unresolved/conflicting fields as unresolved;
3. create a backup;
4. verify migration/schema compatibility;
5. selectively publish reviewed canonical/profile/evidence state;
6. run normal migration, API, RLS, and full-stack checks against the target;
7. only then use the published data in hosted runtime.

Collection evidence enters staging/provenance first. Neither a collector nor an LLM may silently overwrite canonical vehicle or repair truth.
