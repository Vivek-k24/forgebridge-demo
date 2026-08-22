# PartGraph Codex Guide

Read this file first. Keep repository context small.

## Product
PartGraph reconstructs a complete repair assembly from verified machine relationships. Current MVP: Honda only, one Civic radiator-area workflow.

## Hard rules
1. Never invent mechanical facts, OEM numbers, torque values, fluid quantities, fitment, interchange, or safety procedures.
2. Mechanical truth comes from versioned structured data with provenance, not from an LLM.
3. Runtime LLM usage is off by default. Do not add model calls to the normal repair workflow.
4. Do not add Neo4j, vector databases, agent frameworks, microservices, Kubernetes, or paid infrastructure without a demonstrated need.
5. Seller listings never override verified fitment. Commerce search starts only after a verified OEM/interchange identity exists.
6. Low-confidence recognition must return unknown / request another photo rather than guess.
7. Preserve HashRouter and GitHub Pages base path `/forgebridge-demo/`.

## Current code map
- `src/data/partGraphDemo.ts` — prototype vehicle, part nodes, typed relationships and source state.
- `src/lib/repairEngine.ts` — deterministic checklist/completeness/graph validation logic.
- `src/pages/partgraph/PartGraphPrototype.tsx` — current interactive product slice.
- `src/styles/partgraph.css` — PartGraph visual system.

## Context discipline
For a task, read only this file plus the files directly involved. Do not reread legacy ForgeBridge/ChangeGraph pages unless the task explicitly concerns them.

Examples:
- repair logic task → `AGENTS.md`, `src/lib/repairEngine.ts`, `src/data/partGraphDemo.ts`
- UI task → `AGENTS.md`, `src/pages/partgraph/PartGraphPrototype.tsx`, `src/styles/partgraph.css`
- data task → `AGENTS.md`, `src/data/partGraphDemo.ts`

## Before finishing
Run:
```bash
npm run lint
npm run build
```
Do not claim they passed unless they actually passed.
