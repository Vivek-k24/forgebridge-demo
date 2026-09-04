# PartGraph

PartGraph is a stateful AI-assisted automotive repair companion. It identifies the exact vehicle configuration, tracks repair state, manages readiness, and preserves repair memory so a user can pause and resume work without losing context.

The product loop:

1. **What do I need?** — verified repair requirements and readiness.
2. **How do I do it?** — verified guidance with safety boundaries.
3. **Where am I now?** — RepairSession state and physical repair memory.

Honda and the 2009 Civic Hybrid are validation cases, not product limits. PartGraph is designed around exact vehicle configurations across supported manufacturers, models, trims, engines, transmissions, and drivetrains.

---

# Current Development Status

## Completed foundations

- React + TypeScript frontend
- FastAPI backend
- PostgreSQL persistence
- Authentication and user isolation
- UserVehicle/Garage system
- Vehicle identity resolution
- RepairSession foundation
- Repair memory
- Inventory/readiness model
- Canonical vehicle configuration model
- Catalog coverage tracking
- Docker local development environment

## Current active work

### Vehicle data coverage workbench

The first research batch contains **363 vehicle configuration candidates** from the selected Asian brands workbook.

Important:

The 363 rows are not considered complete or verified data.

They represent:

```
Candidate configurations
        ↓
Source collection
        ↓
Evidence reconciliation
        ↓
Canonical promotion
```

Collection and verification progress are tracked separately.

Example:

```
Collected: 120 / 363
Verified:  45 / 363
```

A configuration becomes verified only after sufficient independent evidence supports the exact identity.

---

# Local Development

PartGraph is designed to run locally using Docker Compose.

The local environment contains:

```
Browser
   ↓
React Web
   ↓
FastAPI API
   ↓
PostgreSQL

Optional local workers:
   ↓
Collection / evidence processing
```

Local development does not require Vercel or Neon.

Those are deployment targets. Research and development workloads can run on developer hardware first.

Start locally:

```bash
docker compose up --build
```

Services:

- Web: `http://localhost:5173`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

---

# Vehicle Data Collection Workbench

The planned local workbench provides:

- make-level progress tracking
- start/pause/resume controls
- collection job history
- source evidence logs
- failed source tracking
- retry capability
- local source caching
- verification progress

The workbench is not part of the user repair flow.

It exists for controlled research and data preparation.

---

# Verification Model

PartGraph separates:

- source collection
- evidence extraction
- normalization
- conflict detection
- canonical promotion

Three independent source matches are the minimum verification target for ordinary configuration identity. Additional sources may be used when evidence conflicts or remains incomplete.

Conflicts are preserved. The system does not silently guess.

---

# Future Admin Console (Planned)

A separate administrator application is planned.

It will manage operational visibility without exposing internal controls to normal users.

Planned areas:

- user statistics
- active users
- product usage analytics
- repair trends
- vehicle coverage progress
- collection workers
- source monitoring
- AI/LLM usage
- token consumption
- cost tracking
- application errors
- server metrics
- database health
- website analytics
- mobile app analytics
- reports and feedback
- security events
- audit logs
- feature controls

Status:

```
Planned
Not implemented
Separate admin surface
```

---

# Architecture

```
User Application
      |
      v
FastAPI Modular Monolith
      |
      v
PostgreSQL

Local Research Tools
      |
      v
Staging / Evidence Data
```

Canonical truth and private user state remain separate.

Private data:

- UserVehicle
- RepairSession
- Inventory
- Photos
- Repair observations

Canonical data:

- VehicleConfiguration
- Verified repair definitions
- Verified requirements
- Mechanical claims

---

# Documentation

Architecture reference:

`docs/PARTGRAPH_SYSTEM_UML.md`

Engineering rules:

`AGENTS.md`

Future planning:

`docs/ROADMAP.md`

---

# Technology Stack

Frontend:

- React
- TypeScript
- Vite

Backend:

- Python
- FastAPI
- SQLAlchemy
- Alembic

Database:

- PostgreSQL

Infrastructure:

- Docker
- Docker Compose
- GitHub Actions
- GitHub Container Registry

Deployment:

- Vercel
- Neon PostgreSQL

Local research:

- Docker-based worker environment
- Local PostgreSQL state
- Local evidence cache

---

# Engineering Principles

- Exact vehicle identity before repair applicability.
- Evidence before canonical truth.
- Ambiguity is preserved instead of guessed.
- AI assists but does not replace mechanical verification.
- Collection tools never write directly into canonical truth.
- User data and shared vehicle knowledge remain isolated.

---

# Roadmap

Current:

- Complete initial vehicle coverage research batch.
- Improve catalog verification workflows.
- Expand supported configurations.

Future:

- Admin operations console.
- Mobile applications.
- Expanded vehicle coverage.
- Production-scale data operations.
