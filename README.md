# PartGraph

PartGraph is a stateful, data-driven automotive repair platform designed to guide a user through a real repair without losing mechanical context, repair state, inventory state, evidence, or safety boundaries.

It is not designed as a generic automotive chatbot.

The product is built around four questions:

1. **What exact vehicle am I working on?**
2. **What does this repair actually require?**
3. **What is the next supported action?**
4. **What is the physical state of the repair right now?**

PartGraph combines verified automotive knowledge with private, resumable owner repair state.

---

## Project status

The software foundation is substantial, but the MVP is not complete.

Already implemented in meaningful form:

- account signup and sign-in
- server-side authentication sessions
- private owner data isolation
- PostgreSQL row-level security
- Garage / saved vehicle backend
- VIN and manual vehicle identity foundation
- resumable RepairSession lifecycle
- immutable repair event history
- pause / resume
- edit leases for multi-device protection
- repair memory
- inventory and readiness foundations
- deterministic guided-procedure engine
- structured API error codes and request IDs
- staging-versus-canonical data boundaries
- safety / capability policy foundations

Major remaining work includes:

- consolidating historical branches and removing obsolete code paths
- eliminating vehicle-specific facts from application/test logic
- completing exact vehicle applicability handling
- adding first-class downstream repair dependencies
- correcting repair completion semantics
- reconciling inventory/readiness state
- durable private photo storage
- browser end-to-end testing
- restoring offline repair continuity
- human reviewer/curator/admin RBAC
- completing the canonical automotive data pipeline
- building trustworthy repair knowledge for the MVP reference fleet

Current implementation sequencing is maintained in [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## Architecture contract

The canonical architecture is defined in [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md).

The most important rules are:

### Code contains behavior; data contains automotive facts

Application logic must not be written around a particular real vehicle.

Real vehicle identity and mechanical facts belong in databases or approved stored data, including:

- model year
- make
- model
- trim
- engine
- transmission
- drivetrain
- OEM part numbers
- vehicle-specific specifications
- repair procedures

The same application code must work as vehicle coverage expands.

### Missing means missing

PartGraph does not invent a mechanical fact because the user expects an answer.

Conflicting evidence remains conflicting until resolved. Missing evidence remains missing.

### Deterministic repair execution

Once a repair definition is verified, deterministic application logic decides:

- readiness
- blockers
- next supported action
- dependencies
- downstream required operations
- completion state

AI may assist with explanation, extraction, normalization, and candidate generation. It does not choose the next repair step and cannot directly publish canonical mechanical truth.

### Replacement does not automatically mean completion

A component replacement can trigger another required operation.

PartGraph must keep that downstream requirement visible and cannot report a repair as fully complete while known required work remains unresolved.

### Shared knowledge and private owner state are separate

Shared canonical knowledge includes verified vehicle, part, repair, requirement, procedure, specification, evidence, and capability data.

Private owner state includes Garage vehicles, RepairSessions, readiness, inventory, repair memory, observations, progress, and photos.

Private data is protected through authenticated API access and database-level isolation.

### Safety boundaries fail closed

Unsupported or uncertain work must be represented explicitly rather than improvised.

Computer/service-tool programming, coding, relearn, initialization, and similar operations are outside the guided MVP boundary. Purely physical/mechanical work may be guided only when supported by verified data and policy.

---

## System shape

```text
Browser / Device
      |
      v
React + TypeScript Web Application
      |
      v
FastAPI API
      |
      +-----------------------------+
      | Identity / Authentication   |
      | Canonical Knowledge         |
      | Repair Experience           |
      | Assistance                  |
      | Optional Intelligence       |
      +-----------------------------+
      |
      v
PostgreSQL / Neon
      |
      +-- shared canonical knowledge
      +-- source/evidence provenance
      +-- private owner state
      +-- repair event history
      +-- readiness/progress

Private durable object storage
      |
      +-- owner repair media

Offline / operator data pipeline
      |
      +-- source acquisition
      +-- raw evidence
      +-- candidate extraction
      +-- review/conflict handling
      +-- canonical promotion
```

External collectors and LLM providers are not required on the normal deterministic repair-execution path.

---

## Repository layout

```text
api/                 FastAPI backend, domain modules, migrations and API tests
web/                 React + TypeScript frontend
local-validation/    Local end-to-end acceptance harness
.github/workflows/   CI/CD workflows
docs/ROADMAP.md      Implementation sequence and completion gates
docs/BLUEPRINT.md    Canonical architecture and system rules
docs/*.xlsx          Preserved automotive datasets where still present
```

Historical documents, old UMLs, collector notes, branch experiments, and prototypes are not architecture authority unless their useful content has been incorporated into the Blueprint or Roadmap.

---

## Technology stack

### Frontend

- React
- TypeScript
- Vite

### Backend

- Python
- FastAPI
- SQLAlchemy
- Alembic

### Data

- PostgreSQL
- Neon for hosted PostgreSQL

### Infrastructure and validation

- Docker
- Docker Compose
- GitHub Actions
- GitHub Container Registry
- Vercel deployment

---

## Local development

The core application is designed to run locally with Docker Compose.

```bash
docker compose up --build
```

Default local services:

- Web: `http://localhost:5173`
- API: `http://localhost:8000`
- API documentation: `http://localhost:8000/docs`

Local development must not require production owner data.

---

## Data trust model

PartGraph separates raw observations from canonical truth.

```text
External source
      |
      v
Raw / staging evidence
      |
      v
Candidate fact
      |
      v
Applicability + authority review
      |
      +---- conflict / reject / needs review
      |
      v
Verified evidence
      |
      v
Canonical mechanical claim
      |
      v
Versioned repair knowledge
```

Collectors may place information into staging. They do not have authority to publish canonical truth directly.

---

## Error, timeout and degraded-operation model

PartGraph uses machine-readable failures rather than relying only on text messages.

A normal API error includes:

```text
code
message
request_id
retryable
details
```

The browser has a bounded request timeout. Safe reads may use bounded retry behavior. Ambiguous writes must be reconciled against authoritative server state rather than blindly retried.

Offline continuity is part of the target architecture. The server remains authoritative; offline repair packs are versioned working copies, not a second source of truth.

See the Blueprint for the full resilience contract.

---

## Security and isolation model

Private owner data uses defense in depth:

```text
Authenticated browser
      |
      v
API authentication + CSRF/origin checks
      |
      v
restricted application database role
      |
      v
transaction-local owner identity
      |
      v
PostgreSQL FORCE ROW LEVEL SECURITY
      |
      v
owner-private rows
```

Human curation roles are being expanded beyond normal owner authorization to separate contributor, reviewer, curator, and operator/admin authority.

---

## Documentation authority

There are two primary project documents:

- **[`docs/BLUEPRINT.md`](docs/BLUEPRINT.md)** — what PartGraph is and how it is designed.
- **[`docs/ROADMAP.md`](docs/ROADMAP.md)** — the order in which the remaining work is implemented and validated.

The Blueprint controls architecture. The Roadmap controls sequencing.

A roadmap update must not silently change the architecture contract.

---

## Development principle

PartGraph should become broader by adding trustworthy data, not by adding vehicle-specific application branches.

A new vehicle should be primarily a **data coverage problem**, not another software architecture rewrite.
