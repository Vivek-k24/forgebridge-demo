# PartGraph System Blueprint

Status: Canonical architecture contract  
Roadmap: `docs/ROADMAP.md`

## 1. Product definition

PartGraph is a universal, data-driven automotive repair platform.

Application code must not know that a particular real vehicle exists. Code knows schemas, relationships, state machines, authorization rules and algorithms. Vehicle identity and mechanical facts come from databases or approved stored data.

The MVP reference fleet is validation data, not architecture:
- 2009 Honda Civic
- 2015 Toyota Camry
- 2018 Ford F-150
- 2020 Subaru Forester
- 2022 Hyundai Tucson

The first deep validation configuration is the 2009 Honda Civic Hybrid.

## 2. Non-negotiable invariants

### 2.1 Code contains behavior; data contains automotive facts

Do not hard-code real:
- year
- make
- model
- trim
- engine
- transmission
- drivetrain
- OEM part number
- vehicle-specific torque/capacity/specification
- repair procedure fact

in application logic, frontend logic, tests or CI logic.

Reference vehicles are loaded through fixtures/data records.

### 2.2 Missing means missing

PartGraph must never infer a mechanical fact merely because an answer is expected.

A fact may be:
- verified
- staged
- needs review
- conflicting
- rejected
- superseded
- missing

Missing/conflicting truth is a valid runtime result.

### 2.3 Deterministic execution

Once a repair definition is verified, deterministic code chooses:
- readiness
- blockers
- next action
- prerequisites
- downstream required operations
- completion state

An LLM may explain or propose candidate knowledge. It does not choose the next repair step and cannot directly write canonical truth.

### 2.4 Replacement is not completion

Replacing a component can trigger another required operation.

PartGraph must model:
- operation requires operation
- repair triggers operation
- repair triggers repair
- required before completion
- required but unsupported/deferred

The application cannot claim full mechanical completion while a known required downstream operation remains.

### 2.5 Safety/capability boundaries

MVP rules:
- computer/service-tool programming, coding, relearn, initialization or calibration: unsupported
- high-voltage hybrid internal service: unsupported
- purely physical/mechanical bleeding: may be supported when verified
- aiming, adjustment, priming and specialized torque-sequence guidance: deferred unless policy changes

An unsupported boundary is not a completable procedure action.

## 3. System topology

```text
Browser / Device
      |
      | HTTPS + HttpOnly session cookie
      v
React + TypeScript Web Application
      |
      | versioned API contract
      v
FastAPI Modular Monolith
      |
      +--------- Identity / Auth
      +--------- Canonical Knowledge
      +--------- Repair Experience
      +--------- Assistance
      +--------- Intelligence Gateway
      |
      v
PostgreSQL / Neon
      |
      +-- shared canonical automotive knowledge
      +-- staging/evidence provenance
      +-- private owner state
      +-- repair event history
      +-- readiness/progress
      +-- audit state

Private Durable Object Storage
      |
      +-- repair photos/media

Operator / Offline Data Pipeline
      |
      +-- source acquisition
      +-- raw immutable evidence
      +-- extraction/candidate facts
      +-- review/conflict resolution
      +-- canonical promotion
      +-- repair-definition materialization
```

No external collector or LLM is required on the normal guided-repair execution path.

## 4. Data planes

### 4.1 Shared canonical knowledge

Shared across users and read-only to ordinary user workflows.

Includes:
- vehicle configurations
- systems/assemblies
- components/parts
- fitment
- specifications
- sources
- evidence
- mechanical claims
- repair definitions
- operations
- requirements
- procedure actions/dependencies
- downstream dependencies
- capability policies

### 4.2 Private owner state

Owner-scoped:
- account preferences
- UserVehicles
- encrypted VIN state
- Garage inventory
- RepairSessions
- event history
- readiness
- procedure progress
- fastener/storage memory
- observations
- photos
- AI invocation audit

### 4.3 Candidate/staging data

Untrusted until promoted:
- ingestion batches
- raw source records
- extraction output
- candidate identity/facts
- source metadata

Collector services must not have direct canonical publishing authority.

## 5. Authorization and isolation

Defense in depth:

```text
Browser
  |
  | HttpOnly cookie + CSRF + Origin
  v
Authentication
  |
  v
SET LOCAL ROLE partgraph_app
  |
  v
SET LOCAL partgraph.user_id=<authenticated user>
  |
  v
PostgreSQL FORCE ROW LEVEL SECURITY
  |
  v
Owner-private rows
```

Every new private table must:
1. contain an owner key or derive ownership through a protected relation
2. use RLS or an equally strong database-enforced boundary
3. be queried through authenticated API services
4. receive adversarial cross-owner tests

### Human RBAC

Target human roles:

Owner/User
- manage own Garage
- run own repairs
- manage own inventory/memory/photos

Contributor
- submit candidate corrections/evidence
- cannot verify/publish

Reviewer
- review evidence/candidate claims
- accept/reject review items
- cannot bypass provenance

Curator
- resolve source-supported conflicts
- build/version canonical repair definitions
- publish verified knowledge

Operator/Admin
- source registration
- pipeline/job controls
- operational/account administration where required

Collector Service
- staging write capability only
- no canonical authority

UI hiding is not authorization. Enforcement belongs in API/domain logic and database privileges where practical.

## 6. Failure and error contract

Every API failure uses a structured envelope:

```text
error:
  code
  message
  request_id
  retryable
  details
```

Rules:
- HTTP status communicates transport/category meaning
- `error.code` communicates exact PartGraph condition
- `message` is safe for the user
- `request_id` links frontend, API and logs
- `retryable` is explicit
- `details` is structured and non-secret
- unknown exceptions become a controlled internal error
- no raw stack trace is returned to users

Error codes are an API contract and must come from a central registry.

Examples of families:
- REQUEST_*
- AUTH_*
- VEHICLE_*
- VIN_*
- USER_VEHICLE_*
- REPAIR_SESSION_*
- STORAGE_/FASTENER_/INVENTORY_/OBSERVATION_/PHOTO_*
- KNOWLEDGE_*
- PROCEDURE_*
- RBAC_*
- OFFLINE_/SYNC_*

## 7. Timeout, retry and recovery contract

### Browser request deadline

Current hard blocking limit: 10 seconds.

### Performance thresholds

- >= 3 seconds: slow-request warning
- >= 10 seconds: hard-boundary warning/deadline condition

### External dependencies

External services receive smaller dedicated timeout budgets. Their timeout must not consume the entire user-facing request budget.

### Retry rules

Safe/idempotent reads:
- bounded automatic retry is allowed

Mutations:
- never blindly retry an ambiguous write

Required write-timeout flow:

```text
write sent
   |
   X timeout / connection lost
   |
   v
query authoritative state using idempotency key/state
   |
   +-- committed -> return/display committed state
   +-- definitely absent -> retry with SAME idempotency key
   +-- uncertain -> degraded state; do not guess
```

Every important mutation must be idempotent or provide an equivalent safe reconciliation mechanism.

## 8. Offline contract

The server remains authoritative.

Offline support is restored through a versioned repair pack rather than by moving authority into browser state.

### Offline repair pack may contain

Shared verified data:
- versioned RepairDefinition
- procedure actions/dependencies
- requirements
- warnings
- capability boundaries
- supporting diagrams/assets approved for offline use

Private cached state:
- last confirmed session checkpoint
- readiness snapshot
- repair-memory summary
- last confirmed progress sequence

### Offline UI requirements

Always show:
- OFFLINE state
- last successful sync time
- repair-definition/version identifier

Never:
- invent newer canonical knowledge
- report unsynced server writes as committed
- bypass a safety boundary

### Offline writes

Initial MVP offline mode should be read-safe.

If offline mutation is enabled later, it requires:
- local immutable event journal
- local event IDs/idempotency keys
- server base sequence
- device identity
- conflict detection
- deterministic reconciliation
- explicit user resolution where automatic merge is unsafe

## 9. The 18-domain automotive data model

### Domain 1 — Vehicle identity and exact configuration
market, model year, make, model, trim/series, generation/platform, body style, engine, transmission, drivetrain, VIN-derived observations.

### Domain 2 — Systems, subsystems, assemblies and subassemblies
physical hierarchy and placement.

### Domain 3 — Parts and component identity
canonical component identity, OEM/manufacturer observations, part-number observations, position and revision.

### Domain 4 — Fitment and applicability
exact configuration applicability, exclusions and qualifiers.

### Domain 5 — Interchange, supersession and replacement identity
supersedes, superseded-by, valid interchange and service replacement.

### Domain 6 — Physical and mechanical relationship graph
contains, attached-to, sealed-by, fastened-by, fluid-connected-to, electrically-connected-to, remove-before and related edges.

### Domain 7 — Fasteners, hardware, seals and clips
canonical small hardware plus owner/session physical state.

### Domain 8 — Tools, equipment and workspace
hand tools, specialty tools, lifting/support, safety equipment and workspace requirements.

### Domain 9 — Fluids, lubricants, refrigerants, materials and consumables
specification, quantity/capacity, compatibility, consumption and disposal/safety metadata.

### Domain 10 — Specifications, limits and measurements
torque, pressure, flow, clearance, dimensions, capacity, service limits and electrical values.

### Domain 11 — Repair definitions and operations
versioned, applicable canonical repair definition and constituent operations.

### Domain 12 — Procedure actions, ordering and dependencies
deterministic action graph with requirements, warnings, evidence, blockers and skippability.

### Domain 13 — Triggered/downstream required operations and completion
cross-operation and cross-repair dependencies and completion blockers.

### Domain 14 — Diagnostics, symptoms, DTCs, inspections and observations
observed symptoms, DTC records, inspections, measurements and confirmed/suspected cause relationships.

### Domain 15 — Electrical, sensors, connectors and control boundaries
serviceable physical electrical data while separating unsupported computer-controlled operations.

### Domain 16 — Safety, capability and procedure boundaries
supported, information-only, professional-required, prohibited and unsupported-indefinitely policy.

### Domain 17 — Provenance, evidence, authority, conflicts and versioning
source identity/class, raw observation, extracted candidate, exact claim, applicability, review decision, conflicts and supersession.

### Domain 18 — Owner Garage, session, inventory, memory, readiness and progress
all private state needed to execute and resume a real repair.

## 10. Software modules

### Application composition
`partgraph.main`
- application construction
- middleware
- routers
- health/version endpoints

`partgraph.database`
- engine/session configuration
- transaction infrastructure

`partgraph.orm_registry`
- complete ORM metadata registration

### Identity
`partgraph.identity.auth`
- registration/login/session
- password hashing
- CSRF/origin
- owner context
- human RBAC integration

`partgraph.identity.vehicle`
- canonical identity
- normalization
- exact resolution
- data-driven selectable coverage

`partgraph.identity.user_vehicle`
- private Garage vehicle
- VIN encryption/cache
- archive/duplicate protection

### Knowledge
`partgraph.knowledge.sources`
`partgraph.knowledge.staging`
`partgraph.knowledge.evidence`
`partgraph.knowledge.claims`
`partgraph.knowledge.vehicle_structure`
`partgraph.knowledge.parts`
`partgraph.knowledge.fitment`
`partgraph.knowledge.interchange`
`partgraph.knowledge.relationships`
`partgraph.knowledge.hardware`
`partgraph.knowledge.requirements`
`partgraph.knowledge.repair`
`partgraph.knowledge.procedure`
`partgraph.knowledge.downstream`
`partgraph.knowledge.diagnostics`
`partgraph.knowledge.electrical`
`partgraph.knowledge.specifications`
`partgraph.knowledge.materials`
`partgraph.knowledge.capability`

### Repair experience
`partgraph.repair_experience.sessions`
`partgraph.repair_experience.events`
`partgraph.repair_experience.projection`
`partgraph.repair_experience.lease`
`partgraph.repair_experience.readiness`
`partgraph.repair_experience.inventory`
`partgraph.repair_experience.progress`
`partgraph.repair_experience.memory`
`partgraph.repair_experience.media`
`partgraph.repair_experience.reorientation`
`partgraph.repair_experience.offline`

### Assistance
`partgraph.assistance`
- deterministic explanation of canonical state
- no authority to change repair truth

### Intelligence
`partgraph.intelligence`
- optional provider-neutral AI gateway
- extraction/proposal/explanation assistance
- invocation audit
- no direct canonical writes
- no next-step authority

### Data curation/operator path
- source acquisition
- immutable raw storage
- extraction
- candidate generation
- review
- conflict resolution
- promotion
- repair materialization

## 11. Core user workflows

### Account
register -> authenticate -> server session -> private workspace

### Add vehicle manually
data-driven selector -> normalize -> exact match/ambiguity -> owner save

### Add vehicle by VIN
validate -> bounded provider decode -> normalize -> exact resolution -> encrypted/fingerprinted owner save

### Start repair
saved vehicle -> create session -> fetch exact verified repair options -> bind versioned repair definition

### Readiness
repair definition -> requirement manifest -> Garage/session inventory reconciliation -> blockers

### Guided repair
capability check -> deterministic next available action -> user update -> immutable event -> recalculate graph

### Pause/resume
pause -> preserve private state -> resume snapshot -> checkpoint/memory/blockers/next supported action

### Downstream trigger
completed physical operation -> activate required downstream edge -> supported action OR explicit unsupported boundary -> completion reevaluation

### Photo
authenticate -> validate -> durable private object storage -> owner-protected metadata -> authorized read/delete

### Canonical ingestion
source registration -> raw capture -> extract candidate -> review applicability/authority -> conflict handling -> verify -> materialize repair

## 12. Completion semantics

Do not use one ambiguous boolean for all completion.

Required conceptual states:
- not started
- active
- blocked
- physical replacement performed
- supported PartGraph work complete
- downstream required work pending
- unsupported/deferred downstream work present
- fully mechanically complete
- archived

A repair cannot become fully complete merely because every UI action was clicked.

## 13. Evidence and publication rules

Canonical publication requires:
1. source is registered
2. authority class is acceptable for the fact/risk
3. exact applicability is established
4. evidence is immutable/auditable
5. conflict state is resolved or intentionally blocks publication
6. fact is explicitly supported by evidence
7. reviewer/curator authorization is valid
8. published version is immutable except through supersession

No majority-vote or AI-confidence shortcut.

## 14. Testing architecture

Required layers:
- unit/domain tests
- API tests
- auth/security tests
- RLS cross-owner tests
- migration tests
- integration Compose
- verified-guidance integration
- browser E2E
- randomized acceptance
- five-model acceptance
- offline/degraded tests
- timeout/reconciliation tests
- RBAC tests
- production-copy migration
- data-free-source-code check

## 15. Deployment rules

- frontend and backend must represent the same source commit
- production owner data is never reset for convenience
- every schema transition is tested on a production copy first
- private media uses durable object storage
- production health has liveness and database readiness
- unavailable external providers must not make existing canonical repair knowledge unavailable

## 16. Architecture authority

This Blueprint is the architecture contract.

Historical README files, old UMLs, workbench docs, collector docs, branch notes and prototypes are not architectural authority after consolidation.

`docs/ROADMAP.md` may change completion order/status without silently changing the rules in this Blueprint.
