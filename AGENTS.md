# PartGraph Codex Guide

Read this file first. Keep repository context small.

## Product
PartGraph reconstructs a complete repair assembly from verified machine relationships. Current coverage is Honda-first and deliberately narrow: one Civic radiator-area workflow.

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

## Current code map
- `src/data/partGraphDemo.ts` — vehicle, part nodes, typed relationships and source state.
- `src/data/partGraphImages.ts` — temporary source-backed preview image references.
- `src/lib/repairEngine.ts` — deterministic checklist/completeness/graph validation logic.
- `src/pages/partgraph/PartGraphPrototype.tsx` — user-facing repair workflow.
- `src/styles/partgraph.css` — responsive PartGraph visual system.

## Context discipline
For a task, read only this file plus the files directly involved. Do not reread legacy ForgeBridge/ChangeGraph pages unless the task explicitly concerns them.

Examples:
- repair logic task → `AGENTS.md`, `src/lib/repairEngine.ts`, `src/data/partGraphDemo.ts`
- UI task → `AGENTS.md`, `src/pages/partgraph/PartGraphPrototype.tsx`, `src/styles/partgraph.css`
- image/part preview task → `AGENTS.md`, `src/data/partGraphImages.ts`, relevant PartGraph UI
- data task → `AGENTS.md`, `src/data/partGraphDemo.ts`

## Token discipline
- Never ask an agent to reread the whole repository for a PartGraph task.
- Reuse verified structured data instead of sending source documents to a model at runtime.
- Use exact files/functions in prompts.
- Any future AI call must log input/output token count and have a deterministic reason for existing.

## Before finishing
Run:
```bash
npm run lint
npm run build
```
Do not claim they passed unless they actually passed.
