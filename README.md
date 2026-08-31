# PartGraph

PartGraph is a stateful AI-assisted automotive repair companion. It identifies the exact vehicle configuration, keeps a durable record of the physical repair, determines verified repair requirements, tracks readiness, and lets the owner resume from the same recorded state after a pause.

The product is organized around three questions:

1. **What do I need?** — verified repair requirements and Inventory readiness.
2. **How do I do it?** — verified procedure guidance and capability safety.
3. **Where am I now?** — RepairSession state, physical repair memory, and Resume/reorientation.

Honda and the 2009 Civic Hybrid are real-world validation cases, not product boundaries. PartGraph is designed for every manufacturer/model/trim/configuration represented by its supported vehicle taxonomy when verified repair data exists for that exact configuration.

## Live application

The authenticated production workspace is:

https://partgraph-main.vercel.app/

That URL is the application entry point. Vercel keeps browser requests on one origin: the React/Vite frontend bundle is proxied from the current-main GitHub Pages artifact, while `/api/*` stays on the production FastAPI service and Neon PostgreSQL database. This lets the existing HttpOnly `SameSite=Lax` session cookie remain first-party instead of weakening authentication for a cross-site frontend/API split.

The GitHub Pages URL remains a static current-main presentation and handoff surface:

https://vivek-k24.github.io/forgebridge-demo/

Direct Pages visits point users to the live Vercel workspace. Pages does not become an authenticated backend host.

## Current architecture

```text
Browser
  │
  ▼
Vercel production origin
  ├── / and /forgebridge-demo/* ──proxy──► GitHub Pages current-main Vite assets
  └── /api/* ────────────────────────────► FastAPI modular monolith
                                                   │
                                                   ▼
                                          Neon PostgreSQL 18

future collector ──staging only──► catalog_staging
```

- `web` — React 19, TypeScript 6, Vite 8; Nginx production container remains tested/published, while the public browser bundle is also published to GitHub Pages.
- `api` — Python 3.14, FastAPI, SQLAlchemy 2, Alembic; hosted on Vercel.
- PostgreSQL 18 — authoritative canonical and private repair state; hosted in Neon for production.
- GitHub Pages — current-main static UI artifact and direct-preview/handoff surface.
- Vercel — same-origin public application entry point and FastAPI runtime.
- `collector` — intentionally not implemented until an approved real ingestion source exists.
- AI/ML — optional future assistance; never canonical mechanical truth and never required for core repair readiness/resume.

PartGraph is server-authoritative rather than offline-first. Redis, Kafka, Kubernetes, Neo4j, and similar infrastructure are not introduced without a measured need.

## Vehicle coverage and applicability

Current product market scope is the United States and Canada, model years 1996 through the current calendar year.

The safety-critical applicability boundary is an exact `VehicleConfiguration`, which can include year, market, manufacturer, model, generation, trim, body style, engine, transmission, and drivetrain as available.

A shared repair name does not make requirements interchangeable. Canonical repair lookup is effectively:

```text
exact VehicleConfiguration + repair_key + verified/current definition version
```

A Honda requirement cannot fall back to a Toyota; a Civic Hybrid requirement cannot silently fall back to another Civic trim or powertrain merely because names look similar. Ambiguous identities remain ambiguous rather than being guessed.

## UserVehicle and VIN

`UserVehicle` is the private owner-specific record. It may resolve to a shared canonical `VehicleConfiguration` or retain an unresolved identity snapshot without creating shared truth.

VIN handling includes:

- 17-character syntax and check-digit validation;
- AES-GCM encryption of the full VIN at rest with explicit key versioning;
- owner-scoped keyed HMAC for duplicate lookup;
- masked VIN / last-six output in normal API and UI surfaces;
- NHTSA vPIC as identity evidence, not automatic canonical truth;
- owner-scoped provider cache with expiry and re-resolution against current canonical identity;
- manual Vehicle Details as a permanent fallback when the provider is unavailable or ambiguous.

## RepairSession and repair memory

A private `RepairSession` belongs to one owner and one `UserVehicle`.

- immutable, ordered repair-session events record lifecycle and physical-state mutations;
- a rebuildable projection provides current state;
- V1 permits one active editing device while other devices may read;
- mutations are lease-protected and idempotent;
- sessions can pause, resume, and archive without rewriting history;
- physical memory includes exceptional fasteners/small parts, storage locations, confirmed observations, photos, and manual inventory fallback;
- Resume/reorientation is a purpose-built read model and does not require a frontend event-history waterfall.

Fasteners and Evidence are backend capabilities, not primary DIY navigation destinations. Ordinary hardware stays in the repair context unless an exception such as missing/damaged hardware needs explicit memory.

## Verified repair definition and readiness

Repair requirements are modeled independently of retailer listings and independently of private possession state.

Canonical relationship:

```text
VehicleConfiguration
  -> RepairDefinition
  -> RepairOperation
  -> RequirementUse
  -> RequirementDefinition
```

Requirements can represent tools, equipment, replacement parts, fluids, consumables, hardware, workspace/setup needs, and safety prerequisites.

A key modeling rule is **not** to model `part -> tool`. A radiator does not inherently require a 10 mm socket; a verified radiator-replacement operation on a specific vehicle configuration may require one.

The repair-level manifest deterministically aggregates verified requirement uses. Reusable items are not multiplied because several operations use them; consumed/replacement quantities aggregate only when the evidence establishes quantity; unknown stays unknown; conflicting semantics fail closed.

A RepairSession can bind once to an exact verified RepairDefinition. The binding is derived from the session's saved vehicle configuration, not from free text, and is version-pinned so a later definition revision cannot silently change an in-progress repair.

### Inventory readiness

Inventory is the primary user-facing readiness workspace. It combines:

```text
verified repair manifest
+ reusable Garage inventory
+ repair-specific readiness state
```

The owner reconciles an aggregated requirement once using `have`, `missing`, `ordered`, or `unavailable`. Reusable tools/equipment/workspace capability can carry forward into Garage inventory; consumables and replacement parts do not automatically become permanent stock. The older manual inventory remains an explicit fallback/exception path when verified repair data is not available.

## Mechanical truth and provenance

PartGraph does not infer mechanical truth from an LLM, retailer listing, similarity, image, or part-number pattern.

Evidence flows through:

```text
source record
-> extracted claim
-> normalized candidate
-> applicability/conflict validation
-> review/promotion
-> MechanicalClaim
-> RequirementUseEvidence
-> canonical requirement
```

Source authority is evaluated separately from parser/model confidence. OEM service information and properly licensed OEM-derived data are the preferred authority for explicit procedure requirements; OEM parts data establishes parts/assembly facts within its scope; retailers are procurement sources after fitment/specification truth exists; community material is discovery/supporting evidence only.

No real catalog/service-data collection, licensing acceptance, paid source activation, or promotion is triggered by normal application use, CI, or deployment. The first real repair-data ingestion remains an explicit licensing/governance gate tracked by issue `#71`.

## Safety boundary

Verified data does not automatically mean PartGraph should guide every procedure. Guided V1 capability excludes or restricts safety/professional-only work such as high-voltage battery/internal inverter service, airbags/SRS/pyrotechnics, immobilizer/security programming, ADAS calibration, structural collision/frame repair guidance, and other explicitly unsupported safety-critical procedures.

## Visual architecture

The living end-to-end visual map is:

[`docs/PARTGRAPH_SYSTEM_UML.md`](docs/PARTGRAPH_SYSTEM_UML.md)

It contains Mermaid diagrams for the product loop, canonical/private data model, manufacturer applicability, evidence promotion, readiness reconciliation, pause/resume flow, components, and block dependencies. GitHub issues/PRs remain the execution source of truth; the UML is the visual architecture map rather than a separate Scrum/Kanban storyboard.

## Current roadmap

- Blocks 2–5: vehicle identity, trust boundary, authentication/isolation, UserVehicle/VIN — complete.
- Block 6 collector — deferred until an approved real ingestion source exists.
- Blocks 7–9: RepairSession, physical repair memory, Resume/reorientation — complete.
- Blocks 10–11: deterministic verified repair/readiness/procedure foundations — implemented; production repair content remains fail-closed until licensed source approval and exact applicability are available.
- Block 12: deterministic assistance/intelligence boundary is established; external model providers, training, embeddings, and autonomous agents remain deferred.
- Production runtime: Vercel FastAPI + Neon PostgreSQL + same-origin web entry point — active.
- Cross-cutting security/performance/mobile/end-to-end quality gates apply continuously.

See GitHub issue `#71` for the repair-data licensing gate and `docs/PARTGRAPH_SYSTEM_UML.md` for the current bounded architecture.

## Run locally

Requirements: Docker Desktop with Docker Compose.

PartGraph starts without VIN secrets, but VIN operations fail closed until runtime keys are supplied. For Windows PowerShell:

```powershell
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
function New-PartGraphKey {
    $bytes = New-Object byte[] 32
    $rng.GetBytes($bytes)
    [Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_')
}
$vinEncryptionKey = New-PartGraphKey
$vinLookupKey = New-PartGraphKey
$env:PARTGRAPH_VIN_ENCRYPTION_KEYS = "{`"1`":`"$vinEncryptionKey`"}"
$env:PARTGRAPH_VIN_ACTIVE_KEY_VERSION = "1"
$env:PARTGRAPH_VIN_LOOKUP_KEY = $vinLookupKey

docker compose up --build
```

For Bash/zsh:

```bash
VIN_ENCRYPTION_KEY="$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')"
VIN_LOOKUP_KEY="$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n')"
export PARTGRAPH_VIN_ENCRYPTION_KEYS="{\"1\":\"${VIN_ENCRYPTION_KEY}\"}"
export PARTGRAPH_VIN_ACTIVE_KEY_VERSION=1
export PARTGRAPH_VIN_LOOKUP_KEY="${VIN_LOOKUP_KEY}"

docker compose up --build
```

Open:

- Web: `http://localhost:5173`
- API readiness: `http://localhost:8000/api/v1/health/ready`
- Supported brands: `http://localhost:8000/api/v1/vehicle-brands`
- API docs: `http://localhost:8000/docs`

The Vite development server proxies `/api/*` to `http://localhost:8000`, matching the same-origin browser contract used in production.

Stop with:

```bash
docker compose down
```

The PostgreSQL volume is retained. Use `docker compose down -v` only when intentionally deleting local database data. Keep VIN keys stable for as long as rows encrypted by those keys need to remain decryptable.

## Public surfaces

- **Live authenticated application:** https://partgraph-main.vercel.app/
- **Static current-main preview / handoff:** https://vivek-k24.github.io/forgebridge-demo/
- **API readiness:** https://partgraph-main.vercel.app/api/v1/health/ready
- **API docs:** https://partgraph-main.vercel.app/docs

The live browser app and `/api/*` share the Vercel production origin. GitHub Pages remains static and does not receive private session cookies.

## CI/CD

GitHub Actions validates the real runtime boundaries before merge:

- **API CI/CD** — dependency integrity, `pip-audit`, Ruff, Alembic upgrade/downgrade/re-upgrade and persisted-history upgrade, PostgreSQL/API/RLS/adversarial tests, API image build and readiness smoke.
- **Web CI/CD** — locked Node install/audit, TypeScript, Vite production build, Nginx image and HTTP/security-header smoke.
- **Integration CI** — real Compose stack, API readiness, Web availability, reverse proxy, and authenticated browser-facing flows.
- **Pages** — builds the static current-main web artifact used for direct preview/handoff and by the Vercel same-origin frontend rewrite.
- **Vercel** — deploys the FastAPI project from `api/`, runs Alembic against the connected Neon database, and proxies the production frontend routes to the current-main Pages artifact.

Successful `main` delivery publishes tested images as `ghcr.io/vivek-k24/partgraph-api:<sha>` / `:main` and `ghcr.io/vivek-k24/partgraph-web:<sha>` / `:main`.

## Merge discipline

1. GitHub issue defines scope and acceptance boundary.
2. Work proceeds in a coherent runnable branch/PR.
3. Applied migration history is preserved; use a forward migration instead of rewriting a migration that may exist on persistent developer volumes.
4. All applicable CI checks must pass on the final changed head.
5. GitHub must report the PR mergeable/ready.
6. User-facing changes receive the required local/runtime verification before the final merge boundary.
7. Red, incomplete, knowingly unverified, or gated work is not merged merely to advance the roadmap.
8. After merge, verify `main` delivery/public-preview behavior where applicable.

## Performance contract

- UI acknowledgment target: under 100 ms where practical.
- searchable selector p95: under 250 ms.
- normal API p95: under 1 second.
- repair Resume p95: under 2 seconds.
- ten seconds: hard blocking boundary.

Collector work, LLM calls, model training, and deployments never belong on the repair-session critical path.

## Technology baseline

- React 19 / TypeScript 6 / Vite 8 / Nginx 1.29
- Python 3.14 / FastAPI / SQLAlchemy 2 / Alembic
- PostgreSQL 18 / Neon production hosting
- Argon2id / AES-GCM VIN protection
- Docker / Docker Compose
- GitHub Actions / GitHub Container Registry / GitHub Pages
- Vercel production runtime and same-origin frontend entry point
