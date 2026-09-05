# PartGraph

PartGraph is a stateful AI-assisted automotive repair companion. It is organized around three owner-facing questions:

1. **What do I need?** — verified repair requirements and readiness.
2. **How do I do it?** — verified procedure guidance constrained by capability/safety policy.
3. **Where am I now?** — persisted RepairSession state, physical repair memory, and deterministic resume/reorientation.

The LLM is optional assistance. It is not the source of canonical vehicle, repair, fitment, or safety truth.

## Live application

- Authenticated production workspace: `https://partgraph-main.vercel.app/`
- Static current-main preview/handoff: `https://vivek-k24.github.io/forgebridge-demo/`

The hosted browser app and `/api/*` use the Vercel production origin so the existing HttpOnly first-party session-cookie model remains intact. Neon PostgreSQL is the hosted authoritative database. Local catalog collection does not run on Vercel or Neon.

## Current development status

Core product foundations include authentication, Garage/vehicle identity, VIN/manual resolution, private repair sessions, readiness/inventory, repair memory, resume/reorientation, verified-guidance boundaries, PostgreSQL persistence, RLS/security controls, and hosted Vercel/Neon compatibility.

The current data focus is **vehicle coverage and technical specification collection**.

The first active research batch contains 363 seed candidates from selected Asian brands for model years 1996-2000:

- Acura: 62
- Honda: 114
- Lexus: 18
- Subaru: 63
- Toyota: 106

These are candidate configurations, not a complete 1996-2000 catalog and not verified merely because they were imported from the workbook.

## Vehicle data pipeline

PartGraph does not expect one website to describe the whole car. Vehicle data is built field by field:

```text
candidate configuration
  -> independent source collection
  -> immutable raw cache + provenance
  -> source-scoped field extraction
  -> deterministic nomenclature/unit normalization
  -> one vote per independent source per field
  -> conflict and source-authority reconciliation
  -> progressive technical vehicle profile
  -> reviewed canonical publication
```

Compound strings such as `1.6L VTEC-E 4-Cyl (115 hp)` are decomposed into independent facts before comparison. Trim, engine, powertrain, transmission, drivetrain, horsepower, dimensions, capacities, chassis, safety hardware, and other technical facts remain separate dimensions.

For ordinary vehicle facts, three independent agreeing sources are the normal automatic verification threshold. **There is no fixed maximum number of sources.** Additional independent sources may be consulted whenever earlier evidence is missing or conflicting. Source wording is normalized conservatively; meaningful distinctions are never merged simply because names look similar.

Manufacturer-authoritative facts such as exact service/fluid specifications keep a separate evidence boundary and are not promoted merely because several generic sites repeat them.

Comfort/convenience equipment such as audio, navigation, seat trim, heated seats, and similar features is outside the core technical profile.

See `docs/local-catalog-workbench.md` for the local research workflow.

## Architecture

Current canonical modules are:

- `partgraph.identity` — authentication, account, canonical vehicle identity, private UserVehicle state, and technical specification reconciliation;
- `partgraph.knowledge` — verified mechanical knowledge, staging/evidence, technical profiles, claims, procedures, requirements, source authority, and capability policy;
- `partgraph.repair_experience` — private RepairSession/readiness/progress/memory/photos/inventory;
- `partgraph.assistance` — deterministic owner-facing explanations;
- `partgraph.intelligence` — optional provider-neutral model infrastructure; deterministic product behavior cannot depend on it.

Shared canonical truth and private owner state remain separate. Exact `VehicleConfiguration` is the mechanical applicability boundary.

The living visual architecture map is `docs/PARTGRAPH_SYSTEM_UML.md`.

## Local vehicle-data workbench

The local stack is:

```text
React/Vite web
    -> FastAPI modular monolith
    -> PostgreSQL

local collector worker
    -> extensible source adapter registry
    -> local raw source cache
    -> staging/evidence/profile state
```

Start/rebuild on Windows:

```powershell
.\scripts\workbench.ps1 start
```

Open:

```text
http://localhost:5173/#/catalog
```

Useful helper commands:

```powershell
.\scripts\workbench.ps1 status
.\scripts\workbench.ps1 logs
.\scripts\workbench.ps1 scale2
.\scripts\workbench.ps1 reprocess
.\scripts\workbench.ps1 backup
.\scripts\workbench.ps1 stop
```

`reprocess` re-runs the current extractor and reconciler over successful cached source captures with zero new web requests. `backup` creates a PostgreSQL custom dump plus the raw cache and repository commit reference under `local-data/exports/<timestamp>/`.

Raw research cache and database dumps stay outside normal Git history. Neon is a later reviewed publication target, not the gathering engine.

## Vehicle identity and privacy

`UserVehicle` is private owner-specific state. It may resolve to a shared canonical `VehicleConfiguration` or retain an unresolved identity snapshot without creating shared truth.

VIN handling includes:

- syntax/check-digit validation;
- AES-GCM encryption of full VIN at rest with explicit key versioning;
- owner-scoped keyed HMAC for duplicate lookup;
- masked/last-six output in normal API/UI surfaces;
- NHTSA vPIC as identity evidence, not automatic canonical truth;
- manual vehicle details as a permanent fallback when provider evidence is unavailable or ambiguous.

Full VIN material does not belong in normal logs, analytics, cache keys, or LLM prompts.

## RepairSession and readiness

A private `RepairSession` belongs to one owner and one `UserVehicle`. Immutable ordered events record lifecycle and physical-state changes; current state is rebuildable from history. Mutations are lease-protected and idempotent. Sessions can pause/resume/archive without rewriting history.

Verified repair truth uses:

```text
VehicleConfiguration
  -> RepairDefinition
  -> RepairOperation
  -> RequirementUse
  -> RequirementDefinition
```

Inventory is the main readiness surface and combines the verified repair manifest, reusable Garage inventory, and repair-specific readiness state.

A part does not inherently require a tool. A verified repair operation for an exact vehicle configuration may require one.

## Mechanical truth and source authority

Evidence enters staging/provenance before any canonical promotion:

```text
source record
  -> extracted observation/claim
  -> normalized candidate
  -> applicability + conflict validation
  -> review/promotion
  -> verified evidence / MechanicalClaim / technical profile
  -> canonical consumer
```

A reachable page is not a verification vote. One site cannot satisfy a three-source threshold through reruns or duplicate pages. Conflicts remain visible and unresolved until the applicable evidence policy resolves them.

Blocked/authenticated/paywalled/CAPTCHA-protected sources are not bypassed. Paid source activation or spend requires explicit approval.

Exact repair procedures, torque values, fluids, fitment, safety-critical claims, and repair requirements retain their domain-specific authority gates even when a vehicle configuration profile is well corroborated.

## Safety boundary

Guided capability excludes or restricts professional/safety-critical work such as high-voltage battery/internal inverter service, airbags/SRS/pyrotechnics, immobilizer/security programming, ADAS calibration, structural collision/frame repair guidance, and other explicitly unsupported procedures.

An LLM explanation cannot bypass a deterministic capability restriction.

## Technology baseline

- React 19 / TypeScript 6 / Vite 8 / Nginx
- Python 3.14 / FastAPI / SQLAlchemy 2 / Alembic
- PostgreSQL 18 / Neon production hosting
- Argon2id / AES-GCM VIN protection
- Docker / Docker Compose
- GitHub Actions / GitHub Container Registry / GitHub Pages
- Vercel production runtime

## Merge discipline

1. Scope and acceptance boundary are explicit.
2. Work proceeds in coherent runnable branches/PRs.
3. Applied Alembic history is preserved; later fixes use forward migrations.
4. Applicable CI checks pass on the final changed head.
5. GitHub reports the PR mergeable/ready.
6. User-facing changes receive required local/runtime validation.
7. Red, incomplete, knowingly unverified, or gated work remains unmerged.
8. After merge, verify `main` delivery/public runtime where applicable.

## Roadmap

Near-term sequence:

1. prove the field-level local vehicle collection/reconciliation pipeline on the 363-candidate batch;
2. expand source adapters and technical-profile coverage while preserving source authority;
3. broaden vehicle coverage across the supported US/Canada taxonomy;
4. selectively publish reviewed verified data to Neon;
5. expand verified repair definitions, requirements, procedures, and part applicability;
6. add the planned separate Admin Console for operations/catalog review;
7. extend the existing API-driven product to mobile clients without duplicating canonical business logic.

See `docs/ROADMAP.md` and `docs/PARTGRAPH_SYSTEM_UML.md` for current planning and architecture detail.
