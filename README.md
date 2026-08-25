# PartGraph

PartGraph is a stateful AI-assisted repair companion that reconstructs the exact vehicle assembly, tracks every part and repair action as you work, and lets you stop for days or weeks and resume from the same step, same part, and same fastener.

## Current state

**Block 0: repository reset.** The previous prototype application, generated Honda catalog files, browser-side catalog repositories, repair-specific static data, scraping scripts, and automated deployment/catalog workflows have been removed from the active codebase.

The successful 6th-generation Civic drivetrain collection from the previous architecture is preserved separately as migration/test data. It is not canonical PartGraph data and is not committed to this repository.

## Architecture direction

PartGraph will use three application boundaries:

- `web` — React + TypeScript user and developer interfaces.
- `api` — Python application implemented as a modular monolith for vehicle identity, canonical catalog, assembly graph, repair state, inventory, evidence, guidance, and learning.
- `collector` — isolated Python catalog-ingestion service that can write staging observations but cannot directly promote canonical mechanical truth.

The collector is not part of the interactive user request path.

## Performance contract

The repair workflow must become useful immediately from local state when possible. Server-backed workflow retrieval targets p95 under 3 seconds. Ten seconds is a hard blocking boundary, not a target: after that point the UI must render verified cached/partial state instead of holding the user behind a spinner.

Catalog collection, model training, and large language model calls must never block repair-session resume.

## Local development

```bash
npm install
npm run dev
```

Validation:

```bash
npm run lint
npm run build
```

## Development rhythm

Each product block is implemented on its own branch and pull request. Pull the branch locally, run it in VS Code, inspect the behavior, and merge only after manual approval.
