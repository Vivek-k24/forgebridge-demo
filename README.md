# PartGraph — Honda MVP

PartGraph is a Honda-first repair-completion prototype. Instead of stopping at “this radiator fits your car,” it models the assembly around a repair target so the user can determine what they need, what they already have, what should be inspected, and what must be verified before purchase.

The current branch focuses on one deliberately narrow example: a **2009 Honda Civic 4-door MX Hybrid, US market, KA CVT, front cooling / radiator area**. Part identities marked verified are backed by exact-configuration OEM/dealer catalog pages. Service-manual facts such as torque, coolant capacity, bleed procedure, refrigerant work and hybrid/high-voltage procedures remain locked until authoritative service information is verified.

## Product flow

```text
Vehicle
→ block
→ sub-block
→ target part
→ connected-part checklist
→ repair packet
→ verified OEM/interchange identity
→ five seller links
→ logical exploded view
```

## What V0 now proves

- deterministic vehicle/assembly/part relationship graph
- exact-configuration catalog source ledger with provenance
- source-backed OEM identities for the radiator, mounts, cushions, hoses, fan/shroud components, sensor, drain hardware and adjacent condenser components
- radiator OEM `19010-RRH-901` with five researched purchase/catalog paths
- exact-OEM-number seller searches for other verified parts until provider APIs/adapters are implemented
- `need / have / inspect / not sure` repair-state workflow
- local guest persistence through `localStorage`
- local-only camera preview shell for future constrained part recognition
- logical SVG exploded view driven by the same graph
- graph invariants that reject missing provenance, duplicate IDs/relations and verified records without OEM/source identity

## Architecture

- React + TypeScript + Vite frontend
- deterministic typed part graph
- deterministic repair-state engine
- static/relational graph data; no graph database required
- SVG logical exploded view
- camera-input shell for future constrained visual identification
- commerce adapters only after OEM identity is verified
- runtime language-model usage disabled by design

## Token / compute policy

Normal repair sessions use **zero LLM tokens**. Mechanical truth is precomputed, versioned and cached. Future camera recognition should use constrained local/browser inference where practical. LLMs are reserved for the internal source-ingestion pipeline when deterministic parsing is insufficient, and their output must be human-verified before entering the production graph.

`AGENTS.md` keeps Codex context intentionally small: it directs code tasks to the few files relevant to that subsystem rather than rereading the legacy repository.

## Run locally

```bash
npm install
npm run dev
npm run lint
npm run build
```

GitHub Pages remains configured for the existing `/forgebridge-demo/` repository path.

## Current limitations

- no live Honda/OEM feed; V0 uses curated source-backed catalog records
- no live seller APIs or inventory/price synchronization
- only the main radiator currently has five researched direct purchase/catalog paths
- no repair-manual replacement
- no verified torque, coolant-capacity, bleed, refrigerant or high-voltage procedures yet
- no live computer-vision inference
- exploded view is logically arranged, not dimensional CAD
- catalog-backed part identity does not by itself prove service sequence, reuse policy or torque
- data/licensing rights still need production review before large-scale ingestion

## Next engineering milestone

Build the service-spec source layer for this same radiator workflow and verify the remaining repair semantics before widening vehicle coverage. After that, implement provider adapters/caching, then constrained camera recognition. Do not expand to “all Honda” until this one repair packet survives real-world validation.
