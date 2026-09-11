# PartGraph

PartGraph is a stateful automotive repair platform designed to help people understand, prepare for, perform, pause, and resume real vehicle repairs without losing context.

Instead of treating a repair as a one-time question-and-answer conversation, PartGraph keeps track of the vehicle, the repair being performed, what is required, what has already happened, what remains, and the physical state of the work.

The long-term goal is simple: support repairs across vehicle makes, models, trims, years, engines, transmissions, and drivetrains through structured automotive data rather than vehicle-specific application code.

## What PartGraph offers

PartGraph is organized around six major product areas.

### Garage and vehicle identity

Users can maintain their vehicles in a private Garage and identify them through vehicle details or VIN-based decoding.

### Repair planning and readiness

PartGraph can organize the parts, tools, fluids, consumables, equipment, workspace requirements, and other prerequisites associated with a repair.

### Guided repair

Repairs are represented as structured procedures with dependencies, blockers, warnings, and safety boundaries so the application can guide the user through supported work in the correct context.

### Repair memory

PartGraph remembers the physical state of a repair, including removed hardware, storage locations, observations, inventory state, photos, and repair progress.

### Pause and resume

A repair can be paused and resumed later without requiring the user to reconstruct everything from memory. PartGraph preserves the repair state and helps reorient the user when work continues.

### Verified automotive knowledge

Vehicle identity, repair requirements, procedures, specifications, applicability, and other mechanical facts are designed to come from structured, source-backed automotive knowledge rather than being embedded directly into application code.

## Design principles

PartGraph is built around a few core ideas:

- **Exact vehicle context matters.** A repair must apply to the vehicle configuration being worked on.
- **Evidence comes before mechanical truth.** Missing or conflicting information should remain explicit instead of being guessed.
- **Repair state should survive time.** A user should be able to stop work and return later without losing the physical context of the repair.
- **Replacing a part does not always finish a repair.** A replacement may trigger another required operation before the repair is mechanically complete.
- **Safety boundaries are explicit.** Unsupported or professional-only work should be identified rather than improvised.
- **User data is private.** Personal Garage, repair-session, inventory, observation, and media data is kept separate from shared automotive knowledge.
- **AI is an assistant, not the mechanical source of truth.** Structured verified data and deterministic repair logic remain authoritative.

## Technology

PartGraph currently uses:

- React and TypeScript for the web application
- FastAPI and Python for the API
- PostgreSQL for persistent data
- SQLAlchemy and Alembic for database access and migrations
- Docker and Docker Compose for local development
- GitHub Actions for continuous integration

## Run locally

### Requirements

Install:

- Docker
- Docker Compose

### Start PartGraph

From the repository root:

```bash
docker compose up --build
```

Docker starts the web application, API, and PostgreSQL database.

Open:

- Web application: `http://localhost:5173`
- API: `http://localhost:8000`
- API documentation: `http://localhost:8000/docs`

### Stop PartGraph

```bash
docker compose down
```

## Frontend development

To run the Vite development server separately:

```bash
cd web
npm install
npm run dev
```

The development server runs on `http://localhost:5173` by default.

## Project documentation

The README intentionally stays at the project-overview level.

For the detailed system design, data model, module boundaries, security model, repair behavior, resilience rules, and architecture decisions, see:

- [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md)

For implementation sequencing and project planning, see:

- [`docs/ROADMAP.md`](docs/ROADMAP.md)

## License

Copyright © 2026 Vivek-k24. All rights reserved.

No license is granted to use, copy, modify, distribute, sublicense, or commercially exploit the PartGraph source code or project data without explicit permission from the copyright holder.
