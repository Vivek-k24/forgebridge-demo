# PartGraph

PartGraph helps Honda owners complete a repair assembly without discovering halfway through the job that a mount, cushion, seal, clip, hose, fastener, sensor, or other connected part was missed.

**Live app:** https://vivek-k24.github.io/forgebridge-demo/#/

## Current staged coverage

- **Home (`#/`)** — 6th Generation Honda Civic (1996–2000), U.S. market, Stage 1 front-cooling/radiator workflow.
- **8th-gen (`#/8th-gen`)** — preserved 2009 U.S.-market Honda Civic Hybrid repair workflow with broader catalog-backed adjacent systems.

Coverage is intentionally published in stages. Unsupported assemblies return a clear unavailable state instead of borrowing another trim's data or guessing.

## What PartGraph does

```text
Choose your Honda
→ choose the repair area
→ choose the main part
→ use photo help if you are unsure what a part is called
→ check connected parts and hardware
→ mark Need / Have / Inspect / Not sure
→ open OEM-number-first purchase paths
```

The application separates four trust layers:

1. **Vehicle identity** — exact year/model/configuration and, where useful, VIN evidence.
2. **Part identity and catalog membership** — source-backed OEM numbers, quantities and assembly observations.
3. **Mechanical/service truth** — only published when separately supported by authoritative service/engineering evidence.
4. **Shopping** — seller/search links appear only after the part identity is established.

Seller titles and “fits your vehicle” badges never override verified PartGraph fitment.

## Photos and privacy

Photo help is mobile-first. Current camera/file input stays browser-local; PartGraph does not pretend that automatic recognition is connected when it is not. Future recognition is intended to compare a photo only against parts already valid for the selected vehicle and assembly and to return **unknown** when confidence is insufficient.

## Data pipeline

PartGraph maintains a deterministic Honda vehicle catalog plus a candidate-ingestion pipeline for part observations. Public/dealer catalog pages can corroborate part identity and quantity, but scraped observations are not automatically promoted into mechanical truth.

Runtime repair workflows are designed to use **zero LLM tokens**. Structured extraction, graph traversal, fitment checks, diagrams and OEM-number shopping paths should remain deterministic wherever possible.

## Development

```bash
npm install
npm run dev
npm run lint
npm run build
```

Read `AGENTS.md` before using Codex. It contains the current code map, trust boundaries and token-discipline rules.

PartGraph follows one rule above everything else: **when the system does not have enough evidence to identify a part or relationship safely, it should say so instead of guessing.**
