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

The catalog is union-first: a valid label found on one usable source is retained
instead of being discarded merely because another site blocks requests or uses a
different taxonomy. Source labels and raw captures remain available for review.

This does not weaken canonical mechanical truth. No technical specification or
repair fact is promoted by the identity inventory.

## Source strategy

The first identity pass uses broad enumerators before model pages:

1. NHTSA vPIC enumerates model-year model names.
2. FuelEconomy.gov contributes an independent US model menu and source labels.
3. Kelley Blue Book model-year pages contribute consumer-facing trim/style lists.
4. CarsDirect model-year pages contribute a second consumer-facing trim inventory.

Raw captures are cached under `local-data/workbench/identity/`.

KBB body-style suffixes such as `Sedan 4D`, `Coupe 2D`, and `Sport Utility 4D`
are kept in raw provenance but removed from the canonical trim label. For example,
`HX Coupe 2D` becomes trim `HX`, and `XLE Premium Sport Utility 4D` becomes
`XLE Premium`.

CarsDirect configuration suffixes such as `4dr Sedan`, drivetrain wording, and
body style are handled the same way. They are evidence about the source style, not
part of the trim name.

FuelEconomy labels that only append drivetrain words such as `2WD`, `4WD`, `AWD`,
or `FWD` are mapped back to the corresponding base model when that base model is
present.

A source model ending in `Hybrid` is also folded into the base model when the
same make/year contains that base model. The hybrid marker then travels with its
trim instead of becoming a second model family. For example, the intended 2026
Honda Accord identity is:

```text
Accord
  LX
  SE
  Sport Hybrid
  EX-L Hybrid
  Sport-L Hybrid
  Touring Hybrid
```

This is consistent with PartGraph's existing 2009 Civic Hybrid profile, where
`Civic` is the model and `Hybrid` is a configuration/trim distinction. Names that
are genuinely separate models, such as `Prius Prime`, are not collapsed by this
rule.

The inventory is a discovery dataset first. Missing trim coverage stays visible
instead of being hidden behind a verification percentage. More reviewed model or
trim enumerators can be added without changing the table shape or making them a
new verification gate.

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
