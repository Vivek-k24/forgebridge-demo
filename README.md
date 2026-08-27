# PartGraph

PartGraph is a stateful AI-assisted repair companion that reconstructs the exact vehicle assembly, tracks every part and repair action as work progresses, and lets a repair resume from the same physical state after a pause.

## Current architecture

```text
web (React / TypeScript / Nginx)
        ↓
api (Python / FastAPI modular monolith)
        ↓
PostgreSQL

collector (separate service, not implemented yet)
```

The collector remains outside the interactive user path. No catalog collection runs in the current application.

## Security and private ownership boundary

PartGraph establishes user ownership before storing private vehicle identity.

- Registration uses email + username + password; login accepts username or email.
- Passwords are hashed with Argon2id.
- Authentication uses opaque server-side sessions in an HttpOnly cookie rather than browser-stored bearer tokens.
- State-changing browser requests require PartGraph CSRF validation and an accepted Origin.
- PostgreSQL row-level security (RLS) is defense in depth for user-owned tables.
- Authentication attempts use PostgreSQL-backed rate-limit state that is committed independently from failed request transactions.
- API failures use stable machine-readable codes, request IDs, and an API-version header.
- Private account and vehicle endpoints are `Cache-Control: no-store`.

## Vehicle identity foundation

PartGraph is multi-brand from the skeleton onward. Current market scope is the United States and Canada, with supported model years from 1996 through the current calendar year.

The shared vehicle selector is read-only against canonical data:

1. market and make are controlled by the supported taxonomy;
2. year, model, trim, and optional generation are used to search known configurations;
3. model/trim wording is normalized deterministically for comparison;
4. generation is supporting metadata and is not required to establish a fitment match;
5. ambiguous variants are surfaced instead of guessed;
6. unknown manual model/trim text remains a candidate and does not create shared canonical truth.

## Private UserVehicle and VIN boundary

A `UserVehicle` is the private owner-specific vehicle record. It may point at one known canonical configuration or retain an unresolved normalized identity snapshot without changing shared vehicle truth.

VIN handling is deliberately stricter than ordinary vehicle text:

- the 17-character VIN syntax and check digit are validated before an external request;
- full VINs are encrypted at rest with AES-GCM and an explicit key version;
- duplicate lookup uses an owner-scoped keyed HMAC rather than plaintext VIN;
- encryption authentication data is also bound to the owner ID;
- normal API/UI output exposes only a masked VIN / last six characters;
- runtime encryption and lookup keys are never committed to the repository;
- NHTSA vPIC `DecodeVinValuesExtended` is the first VIN identity provider;
- provider output is normalized through PartGraph's vehicle rules and used only as identity evidence;
- ambiguous or unknown provider results never create canonical vehicle configurations;
- successful provider observations are cached per owner with RLS and expiry, then re-resolved against current canonical data on reuse;
- provider timeout/unavailability never removes the manual Vehicle Details path;
- saved vehicles are archived rather than hard-deleted so later repair history can retain a stable owner vehicle reference.

## Catalog trust boundary

Catalog collection is not implemented or invoked yet. PostgreSQL contains a separate `catalog_staging` schema for future collector output.

- `catalog_staging.ingestion_batches` records source and ingestion-run provenance.
- `catalog_staging.source_records` preserves raw evidence, normalized candidate data, vehicle context, extraction method, confidence, timestamps, review state, and deterministic deduplication.
- `public.catalog_verified_evidence` is an immutable snapshot created only by an explicit verification/promotion operation. It is evidence for future canonical catalog entities; it is not itself a claim that a part or fitment is mechanically correct.
- the database group role `partgraph_collector` can write the staging schema but has no write privilege on canonical vehicle data or verified evidence.
- rejected staging records cannot be promoted in place, and identical source evidence is idempotently deduplicated.

There is intentionally no public staging/promotion API before administrative authorization exists. The preserved historical catalog artifact is not imported or modified by this block.

## Run locally

Requirements: Docker Desktop with Docker Compose.

PartGraph can start without VIN secrets, but VIN operations intentionally fail closed until runtime keys are supplied. For a Block 5 VIN test on Windows PowerShell, generate temporary 256-bit keys in the current terminal:

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

These commands create local test secrets only; do not commit them. Keep the same keys for as long as you need to decrypt VIN rows created with them. Production key rotation belongs in runtime secret management, not Git history.

Open:

- Web: `http://localhost:5173`
- API readiness: `http://localhost:8000/api/v1/health/ready`
- Supported brands: `http://localhost:8000/api/v1/vehicle-brands`
- API docs: `http://localhost:8000/docs`

The production Web container serves the built React application through Nginx. Browser `/api/...` requests are reverse-proxied to the API container, while direct local API access remains available on port 8000.

Stop with:

```bash
docker compose down
```

The PostgreSQL volume is retained between runs. Use `docker compose down -v` only when intentionally deleting local database data.

## CI/CD

GitHub Actions is the automated quality and delivery system.

### API

Workflow: https://github.com/Vivek-k24/forgebridge-demo/actions/workflows/api.yml

On a pull request the API workflow:

- installs the pinned Python test environment and verifies dependency integrity;
- runs `pip-audit` and Ruff;
- applies Alembic migrations and verifies downgrade/re-upgrade behavior;
- runs API, authentication, RLS, VIN, and PostgreSQL boundary tests with warnings treated as failures;
- builds the API Docker image;
- starts the built container and verifies `/api/v1/health/ready`.

After a successful merge to `main`, the same tested source is published as:

- `ghcr.io/vivek-k24/partgraph-api:<commit-sha>`
- `ghcr.io/vivek-k24/partgraph-api:main`

Package: https://github.com/users/Vivek-k24/packages/container/package/partgraph-api

### Web

Workflow: https://github.com/Vivek-k24/forgebridge-demo/actions/workflows/web.yml

On a pull request the Web workflow:

- installs the locked Node dependencies and audits them;
- runs TypeScript type checking;
- performs the production Vite build;
- builds the production Nginx container;
- starts it and verifies HTTP/security headers.

After a successful merge to `main`, the Web image is published as:

- `ghcr.io/vivek-k24/partgraph-web:<commit-sha>`
- `ghcr.io/vivek-k24/partgraph-web:main`

Package: https://github.com/users/Vivek-k24/packages/container/package/partgraph-web

### Full-stack integration

Workflow: https://github.com/Vivek-k24/forgebridge-demo/actions/workflows/validate.yml

The integration workflow builds the real Compose stack and verifies direct API readiness, Web availability, the Web-to-API reverse proxy, and authenticated browser-facing integration flows.

A future Collector will receive its own workflow and GHCR package when the service actually exists.

The pipeline currently provides continuous integration and tested container delivery. A public full-stack PartGraph URL requires a runtime host for the API and PostgreSQL; GitHub Actions/GHCR are not themselves an application host.

## Merge discipline

For implementation PRs:

1. define scope in a GitHub issue;
2. branch from current `main`;
3. create the PR as work-in-progress when useful for CI feedback;
4. wait for all applicable Actions workflows to pass;
5. pull and run the block locally;
6. obtain explicit approval to merge;
7. verify GitHub reports the PR mergeable / ready;
8. merge;
9. verify `main` delivery workflows publish the tested images.

## Performance contract

Normal interactive work should remain comfortably below the 10-second hard blocking boundary. Current quality targets include searchable dropdown p95 under 250 ms, normal API p95 under 1 second, and repair resume p95 under 2 seconds once those workflows exist. VIN provider calls have their own shorter timeout so an external service cannot occupy the full application boundary. Collector work, model training, deployments, and LLM calls never belong on the repair-session critical path.

PartGraph is server-authoritative rather than offline-first. Small transient client caches may improve responsiveness or survive short network interruptions, but private repair truth remains in PostgreSQL and the application does not promise full offline repair operation.

## Current technology baseline

- React 19
- Vite 8
- TypeScript 6
- Nginx 1.29
- Python 3.14
- FastAPI
- SQLAlchemy 2
- Alembic
- PostgreSQL 18
- Argon2id
- AES-GCM VIN protection
- Docker / Docker Compose
- GitHub Actions / GitHub Container Registry
