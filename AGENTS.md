# PartGraph Codex Guide

Read this file first. Keep repository context small.

## Product
PartGraph reconstructs a complete repair assembly from verified machine relationships. Current coverage is Honda-first and deliberately narrow: one Civic radiator-area workflow plus several catalog-backed adjacent system graphs.

The public page is the actual user product, not an investor/demo dashboard. A visitor should be able to understand the repair flow without seeing developer architecture, token metrics or prototype narration.

## Hard rules
1. Never invent mechanical facts, OEM numbers, torque values, fluid quantities, fitment, interchange, or safety procedures.
2. Mechanical truth comes from versioned structured data with provenance, not from an LLM.
3. Runtime LLM usage is off by default. Do not add model calls to the normal repair workflow.
4. Do not add Neo4j, vector databases, agent frameworks, microservices, Kubernetes, or paid infrastructure without demonstrated need.
5. Seller listings never override verified fitment. Commerce search starts only after a verified OEM/interchange identity exists.
6. Low-confidence recognition must return unknown / request another photo rather than guess.
7. Preserve HashRouter and GitHub Pages base path `/forgebridge-demo/`.
8. Mobile is a first-class interface because camera capture happens beside the vehicle. Test narrow phone layouts before adding desktop-only interactions.
9. Keep camera/photo help above the assembly checklist. Photo input must remain browser-local until an explicit upload/recognition service exists.
10. Part cards should show what the part looks like whenever a source-backed image is available. Desktop hover may enlarge it; mobile tap must work too.
11. Do not copy third-party product images into the repository without a rights decision. `src/data/partGraphImages.ts` currently references remote source images as a temporary MVP technique.
12. Prefer fewer clicks and less scrolling: default the checklist to items needing attention and keep already-owned parts behind a lightweight filter.
13. Do not expose internal terms such as “V0 shell”, “graph valid”, “runtime LLM calls”, or “planned recognition evidence” in primary user-facing copy.
14. Treat vehicle/catalog metadata, part identity, mechanical service truth, and shopping as separate trust layers.
15. A scraped/public catalog part number is an observation until reviewed. Never auto-promote scraper output into the repair graph.
16. Catalog pages may establish factual part identity/quantity/fitment evidence. They do not establish torque, pressure, fluid, metallurgy, repair order, reuse policy, or safety procedure unless the source explicitly and authoritatively provides that fact.
17. Keep source URL, source type, market/configuration and review status for every ingested catalog observation.
18. Do not bulk-download diagrams or product images without an explicit rights/licensing decision.

## Data trust layers

```text
vehicle metadata
  Honda-published data / NHTSA / EPA-DOE
        ↓
part identity + fitment observations
  official/licensed catalogs preferred; dealer/catalog pages may corroborate
        ↓
human/source verification
        ↓
mechanical/service facts
  separate story; manufacturer service information or another authoritative source
        ↓
shopping
  seller/API results only after identity is established
```

## Current code map
- `src/data/partGraphDemo.ts` — vehicle, part nodes, typed relationships and source state.
- `src/data/partGraphImages.ts` — temporary source-backed preview image references.
- `src/data/partGraphSystems.ts` — published catalog-backed block/sub-block graphs.
- `src/lib/repairEngine.ts` — deterministic checklist/completeness/graph validation logic.
- `src/lib/partGraphRepository.ts` — current graph repository/read-model boundary.
- `src/lib/partCatalogStore.ts` — normalized static catalog identity/fitment read model.
- `src/lib/hondaVehicleService.ts` — NHTSA model/VIN metadata.
- `src/lib/hondaManualConfigurationService.ts` — public manual Honda configuration metadata.
- `src/pages/partgraph/PartGraphPrototype.tsx` — user-facing repair workflow.
- `src/styles/partgraph.css` — responsive PartGraph visual system.
- `catalog/schema.sql` — future SQLite/Cloudflare D1 catalog schema.
- `tools/catalog/` — internal public-catalog candidate ingestion; never publishes directly to repair truth.

## Context discipline
For a task, read only this file plus the files directly involved. Do not reread legacy ForgeBridge/ChangeGraph pages unless the task explicitly concerns them.

Examples:
- repair logic task → `AGENTS.md`, `src/lib/repairEngine.ts`, relevant graph file
- UI task → `AGENTS.md`, `src/pages/partgraph/PartGraphPrototype.tsx`, `src/styles/partgraph.css`
- image/part preview task → `AGENTS.md`, `src/data/partGraphImages.ts`, relevant PartGraph UI
- vehicle metadata task → `AGENTS.md`, `src/lib/hondaVehicleService.ts`, `src/lib/hondaManualConfigurationService.ts`
- catalog ingestion task → `AGENTS.md`, `tools/catalog/`, `catalog/schema.sql`, `src/lib/partCatalogStore.ts`
- mechanical/service story → do not reuse catalog text as authority; add a separately sourced service layer

## Token discipline
- Never ask an agent to reread the whole repository for a PartGraph task.
- Reuse verified structured data instead of sending source documents to a model at runtime.
- Use exact files/functions in prompts.
- Any future AI call must log input/output token count and have a deterministic reason for existing.
- Prefer deterministic extraction for OEM numbers, quantities, URLs and structured catalog fields.
- LLM-assisted ingestion is allowed only for ambiguous internal extraction; output remains candidate data until human verification.

## Before finishing
Run:
```bash
npm run lint
npm run build
```
Do not claim they passed unless they actually passed.
