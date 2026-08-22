# PartGraph — Honda MVP

PartGraph is a Honda-first repair-completion prototype. Instead of stopping at “this radiator fits your car,” it models the assembly around a repair target so the user can determine what they need, what they already have, what should be inspected, and what must be verified before purchase.

The current branch intentionally focuses on one static example: a **2009 Honda Civic Hybrid US-market front cooling / radiator area**. Mechanical relationships are prototype data unless explicitly marked verified. OEM numbers, torque specifications, fluid quantities and other safety-critical facts stay locked until an authoritative source ledger confirms them.

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

Normal repair sessions should use **zero LLM tokens**. Mechanical truth is precomputed, versioned and cached. Future camera recognition should use constrained local/browser inference where practical. LLMs are reserved for the internal source-ingestion pipeline when deterministic parsing is insufficient, and their output must be human-verified before entering the production graph.

## Run locally

```bash
npm install
npm run dev
npm run lint
npm run build
```

GitHub Pages remains configured for the existing `/forgebridge-demo/` repository path.

## Current limitations

- no live Honda/OEM data feed
- no verified OEM numbers in the demo dataset yet
- no live seller APIs
- no repair-manual replacement
- no torque/fluid/refrigerant/high-voltage claims
- no live computer-vision inference
- exploded view is logically arranged, not dimensional CAD

The next engineering milestone is to build a source ledger for one radiator workflow and replace prototype relationships with source-backed, versioned records before enabling exact commerce links.
