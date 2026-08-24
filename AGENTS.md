# PartGraph Codex Guide

Read this file first. Keep repository context small.

## Product
PartGraph reconstructs a complete repair assembly from verified machine relationships. The public page is the user product, not a developer/demo dashboard.

Current staged runtime:
- `/` — 6th Generation Honda Civic (1996–2000) front-cooling Stage 1.
- `/8th-gen` — preserved 2009 U.S.-market Civic Hybrid repair workflow.

## Hard rules
1. Never invent mechanical facts, OEM numbers, torque values, fluid quantities, fitment, interchange, or safety procedures.
2. Mechanical truth comes from versioned structured data with provenance, not from an LLM.
3. Runtime LLM usage is off by default. Do not add model calls to the normal repair workflow.
4. Do not add Neo4j, vector databases, agent frameworks, microservices, Kubernetes, or paid infrastructure without demonstrated need.
5. Seller listings never override verified fitment. Commerce search starts only after a verified OEM/interchange identity exists.
6. Low-confidence recognition must return unknown / request another photo rather than guess.
7. Preserve HashRouter and GitHub Pages base path `/forgebridge-demo/`.
8. Mobile is a first-class interface because camera capture happens beside the vehicle.
9. Keep camera/photo help above the assembly checklist. Photo input stays browser-local until an explicit recognition/upload service exists.
10. Part cards should show source-backed reference imagery where rights permit. Desktop hover and mobile tap should expose a larger preview.
11. Prefer fewer clicks and less scrolling. Keep already-owned parts out of the primary attention path where practical.
12. Do not expose internal engineering/token narration in primary user-facing copy.
13. Treat vehicle metadata, part identity, mechanical service truth, and shopping as separate trust layers.
14. A scraped/public catalog part number is an observation until reviewed. Never auto-promote scraper output into the repair graph.
15. Catalog evidence does not establish torque, pressure, fluid, metallurgy, repair order, reuse policy, or safety procedure unless the source explicitly and authoritatively provides that fact.
16. Keep source URL, source type, market/configuration and review status for every ingested catalog observation.
17. Do not bulk-download diagrams or product images without an explicit rights/licensing decision.
18. Consumer vehicle selectors must use plain structured labels. Keep raw OEM/catalog configuration codes only as provenance/matching data.

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
  separate authoritative service/engineering evidence
        ↓
shopping
  seller/API results only after identity is established
```

## Current code map
- `src/app/App.tsx` — runtime routes.
- `src/pages/partgraph/PartGraphSixthGen.tsx` — current staged 6th-gen user workflow.
- `src/data/hondaCivic6thGen.ts` — 6th-gen Stage 1 cooling data and deterministic identity rules.
- `src/pages/partgraph/PartGraphStep2.tsx` — preserved 8th-gen/2009 Civic Hybrid workflow.
- `src/pages/partgraph/PartGraphSelect.tsx` — shared compact/mobile selector.
- `src/data/partGraphDemo.ts` — 2009 Civic Hybrid part nodes and source state.
- `src/data/partGraphImages.ts` — temporary source-backed preview image references.
- `src/data/partGraphSystems.ts` — published 8th-gen catalog-backed block/sub-block graphs.
- `src/lib/partGraphRepository.ts` — graph repository/read-model boundary.
- `src/lib/partCatalogStore.ts` — normalized static catalog identity/fitment read model.
- `src/lib/hondaCatalogService.ts` and `src/lib/hondaManualConfigurationService.ts` — static Honda catalog/configuration access.
- `src/lib/hondaVehicleService.ts` and `src/lib/hondaVehicleLabels.ts` — vehicle/VIN metadata and consumer labels.
- `catalog/schema.sql` and `tools/catalog/` — internal catalog candidate ingestion/provenance pipeline.
- `public/data/honda/` — generated Honda vehicle configuration catalog.

## Context discipline
For a task, read only this file plus the files directly involved. Legacy ForgeBridge, ChangeGraph, V3/V4 and superseded PartGraph prototype code should not exist on the active branch.

Examples:
- 6th-gen UI/data task → `AGENTS.md`, `PartGraphSixthGen.tsx`, `hondaCivic6thGen.ts`, `partgraph-sixth-gen.css`
- 8th-gen workflow task → `AGENTS.md`, `PartGraphStep2.tsx`, relevant PartGraph data/repository files
- vehicle metadata task → `AGENTS.md`, Honda service/label files only
- catalog ingestion task → `AGENTS.md`, `tools/catalog/`, `catalog/schema.sql`
- mechanical/service story → add separately sourced service data; do not reuse catalog text as authority

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
