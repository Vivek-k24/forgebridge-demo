# PartGraph US identity catalog phase

This phase intentionally pauses technical specification collection and builds the
consumer-facing vehicle identity inventory first.

## Active scope

- Market: United States
- Model years: 1996 through 2027
- Makes: Acura, Honda, Hyundai, Lexus, Subaru, Toyota
- Fields collected in this phase: year, make, model, trim
- Technical specifications, parts, fluids, procedures, and comfort features are out of scope.

The scope is fixed in `partgraph.knowledge.catalog_scope`. Makes outside that set
are not processed by the identity collector.

## Data rule

The identity inventory is not gated by the technical three-source verifier.

The collector keeps source-backed discoveries immediately and records source
provenance/counts. A model or trim may therefore exist in the inventory before it
is corroborated by another source. `discovered` means source-backed; `corroborated`
means at least two independent providers currently support the same normalized
identity label.

This does not weaken canonical mechanical truth. No technical specification or
repair fact is promoted by the identity inventory.

## Source strategy

The first identity pass uses broad enumerators before model pages:

1. NHTSA vPIC enumerates model-year model names.
2. FuelEconomy.gov contributes an independent model menu and source labels.
3. Kelley Blue Book model-year pages contribute consumer-facing trim/style lists.

Raw captures are cached under `local-data/workbench/identity/`. KBB body-style
suffixes such as `Sedan 4D`, `Coupe 2D`, and `Sport Utility 4D` are kept in raw
provenance but removed from the canonical trim label. For example, `HX Coupe 2D`
becomes trim `HX`, and `XLE Premium Sport Utility 4D` becomes `XLE Premium`.

FuelEconomy model labels that only append drivetrain/configuration words such as
`2WD` or `4WD` are mapped back to the corresponding NHTSA base model when that
base model exists. Exact longer NHTSA models are preserved, so a real model such
as `Civic Hybrid` is not collapsed merely because `Civic` also exists.

The inventory is a union-first discovery dataset. Missing trim coverage is visible
instead of being hidden by a verification percentage. Additional trim enumerators
can be added after the first six-make run without changing the data model.

## Local commands

Start the normal local stack without the technical-spec collector:

```powershell
.\scripts\workbench.ps1 start
```

Start or resume the six-make identity run:

```powershell
.\scripts\workbench.ps1 identity-start
```

View progress:

```powershell
.\scripts\workbench.ps1 identity-status
```

Follow the collector log:

```powershell
.\scripts\workbench.ps1 logs
```

Export the current inventory to JSON:

```powershell
.\scripts\workbench.ps1 identity-export
```

The JSON file is written to:

```text
local-data/workbench/identity-catalog.json
```

Force a fresh network pass for the active scope only when needed:

```powershell
.\scripts\workbench.ps1 identity-refresh
```

The run is resumable by make/year. Completed make/year pairs are skipped on a
normal `identity-start`, while failed or interrupted pairs are retried.

## 2027 caveat

2027 is included because it is inside the requested scope. Since the 2027 model
year is still being published by manufacturers during 2026, the 2027 inventory
represents what the configured sources currently expose and should be refreshed as
new 2027 models/trims are released.
