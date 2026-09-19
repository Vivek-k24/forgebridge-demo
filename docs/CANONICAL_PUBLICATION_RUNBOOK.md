# PartGraph Canonical Publication Runbook

Status: Phase 0–7 remediation contract  
Applies to: reviewed automotive knowledge promoted into a persistent PartGraph environment  
Machine-readable companion: `api/data/reference/persistent_publication_plan_v1.json`

## Purpose

Deployment and canonical publication are separate operations.

Deploying PartGraph code, applying Alembic migrations, starting the API, or creating a preview environment **must not publish automotive facts by itself**. Canonical publication is an explicit operator action performed only after the target environment, source authority, evidence, applicability, conflict state, and publication scope have been reviewed.

This runbook makes the persistent-environment policy explicit. It does not authorize production publication, provider activation, broader source automation, or direct canonical SQL writes.

## Current Phase 7 reference scope

The reference vehicle configuration is `7feb13e9-bca0-5d8b-b701-f0260cce5da1`.

The approved Phase 7 reference bundle is defined by these versioned datasets:

- `api/data/reference/2009_honda_civic_hybrid_parts_v1/manifest.json`
- `api/data/reference/2009_honda_civic_hybrid_repairs_v1/manifest.json`
- `api/data/reference/2009_honda_civic_hybrid_profile_v1/canonical_coverage.json`

The complete scoped target represented by those reviewed datasets is:

| Canonical/provenance object | Expected scoped target |
| --- | ---: |
| Immutable verified evidence | 300 |
| MechanicalClaims | 300 |
| Part fitments | 267 |
| Verified repair definitions | 3 |
| Vehicle structure nodes | 3 |
| Vehicle specification values | 2 |

The 300 claim/evidence rows are composed of one vehicle-identity claim, 267 part-fitment claims, 13 repair-requirement claims, 14 repair-procedure claims, three vehicle-structure claims, and two vehicle-specification claims.

## Current long-lived preview classification

As observed on 2026-09-15 after remediation migration `0061_retire_legacy_specs`, the consolidation preview intentionally contains only part of the approved bundle:

- 282 immutable verified evidence rows
- 282 MechanicalClaims for the reference vehicle
- 267 part fitments
- one verified repair definition: `engine-oil-filter-change`
- zero persistent vehicle-structure nodes
- zero persistent vehicle-specification values

Already persistent:

- verified reference vehicle identity
- reviewed OEM part-fitment set
- `engine-oil-filter-change` and its supporting requirement/procedure claims

Approved in repository fixtures and proven in fresh-database runtime CI, but **not yet intentionally published into the long-lived preview**:

- `engine-water-pump-replacement`
- `cooling-system-refill-air-bleed`
- three vehicle-structure claims
- two vehicle-specification claims

If that exact preview snapshot is later chosen for full reference-bundle publication, the expected scoped increment is 18 evidence rows, 18 MechanicalClaims, two repair definitions, three structure nodes, and two specification values.

These counts describe the reviewed reference bundle only. They are not global-database count assertions.

## Preconditions

Do not begin a persistent publication unless all of the following are true.

1. The target environment is named explicitly and publication into that environment has been separately authorized. Deployment authorization alone is insufficient.
2. The target schema revision is compatible with the application revision selected for publication.
3. The target vehicle configuration is the exact reviewed configuration ID. Vehicle year/make/model strings are informational; applicability is keyed by canonical configuration ID.
4. Every source used by the selected facts exists in the source registry with an approved license state.
5. Existing `automation_allowed` values are preserved. Publication approval never converts a manually reviewed source into an automatically collectable source.
6. Every fact selected for publication has immutable verified evidence before a MechanicalClaim is verified.
7. Every MechanicalClaim is explicit, exactly applicable, reviewed, and accepted by the source-authority policy for its domain and risk level.
8. No unresolved claim conflict blocks publication.
9. Canonical writes are executed only through the restricted materializer capability. Ordinary application-role SQL is not a publication path.
10. A pre-publication database recovery point appropriate to the environment exists when the operation is capable of mutating durable shared state. Production additionally requires the production cutover/backup gates in the audit register.

If any precondition is not satisfied, stop. Missing evidence remains missing; do not fill gaps with inference, model output, copied fixture values, or direct SQL.

## Publication sequence

### 1. Preflight

Record:

- target environment and database branch
- application commit
- Alembic revision
- publication-plan version/key
- canonical vehicle configuration ID
- selected dataset versions
- selected repair keys/domains
- operator/curator identity
- expected scoped pre-state and post-state

Compare the selected datasets to `persistent_publication_plan_v1.json`. A changed manifest or changed expected count requires the publication contract and its tests to be reviewed again before execution.

### 2. Promote immutable evidence

For every selected fact, preserve the original source identity, source URL/reference, source class, raw-content hash, capture/fetch time, exact vehicle identity, extraction method, and reviewer provenance in `catalog_verified_evidence`.

Do not synthesize a new raw hash from a normalized fact merely to make a missing source capture look immutable. The evidence boundary exists to preserve what was actually reviewed.

### 3. Create or reuse verified MechanicalClaims

Create or reuse claims through the existing verified-claim publication path. Each claim must link to immutable evidence and retain:

- canonical vehicle configuration ID
- claim domain
- risk classification
- normalized key
- exact applicability
- reviewer identity/timestamp
- repair key where applicable
- verified promotion state

Idempotent reruns must reuse the existing semantic publication rather than creating a second canonical fact for the same evidence/claim identity.

### 4. Materialize canonical records

Use the restricted materializer role/capability and the existing materialization services:

- part-fitment materializer for part applicability
- repair-definition materializer for repair requirements/actions
- vehicle-domain materializer for structure/specification claims
- downstream-requirement materializer where an approved repair explicitly requires another supported physical repair

Do not bypass these services with direct INSERT/UPDATE statements into canonical tables.

### 5. Verify the scoped result

Verification is scoped to the selected vehicle and publication bundle. At minimum verify:

- selected MechanicalClaims all have immutable evidence links
- no selected claim is pending/rejected/superseded unexpectedly
- selected claim domains and repair keys match the approved plan
- canonical records point back to their supporting claims/evidence according to the materializer contract
- the scoped expected target counts match the publication plan
- no unresolved conflict exists for a selected claim
- no source has had its license or automation state broadened by publication

For the current complete Phase 7 reference bundle, the scoped targets are the counts listed above. For the long-lived preview snapshot recorded in the plan, publishing only the currently missing approved subset would add exactly the documented 18 claims/evidence rows, two repair definitions, three structure nodes and two specification values.

### 6. Record the result

Record the publication outcome with:

- environment
- commit/revision
- plan key
- operator/curator
- selected scope
- before/after scoped counts
- materializer idempotency keys or publication identifiers
- conflicts or skipped claims
- verification result

A failed or partial run is not converted to success by manually editing counts or canonical rows.

## Idempotency

Publication services already enforce idempotent materialization boundaries. Re-running an identical approved publication scope must converge on the same semantic canonical state.

The publication plan is not itself an idempotency key. Use stable operation-specific idempotency keys generated by the publication executor/operator workflow and retain them in the publication record.

## Correction and rollback

Automotive truth corrections should normally be forward-moving:

1. preserve prior evidence and claims;
2. add corrected evidence/claim state;
3. explicitly resolve/supersede the affected claim where required;
4. rematerialize through the governed publication path.

Do not delete provenance merely to make a newer fact appear uncontested.

Database restoration is reserved for an environment-level failed publication/cutover where transactional or operational recovery requires returning the entire environment to a known recovery point. It is not the normal mechanism for correcting one automotive fact.

## What deployment is allowed to do

Deployment may install application code and, until the migration remediation category is completed, may still follow the repository's existing schema-deployment mechanics. Deployment must not:

- automatically load the reference repair fixtures into canonical tables
- automatically turn fixture-only structure/specification facts into persistent canonical data
- enable a source/provider that was disabled
- change `automation_allowed=false` to true
- manufacture evidence for a missing fact
- invoke a materializer solely because a code deployment occurred

Schema migration/deployment coupling is tracked separately as `PG-AUD-DEP-002`; this runbook does not declare that issue resolved.

## CI proof versus persistent publication

The reference-runtime and canonical-publication workflows use fresh databases to prove the same policy and materializer paths without mutating the long-lived preview or production database. Those tests prove implementation behavior; they do not constitute environment publication.

The machine-readable publication-plan test verifies that the plan's vehicle ID, repair list, claim counts and expected target remain consistent with the reviewed versioned datasets.

## Deferred execution automation

A reusable operator-facing persistent bundle publisher is intentionally deferred to **Phase 6 broad canonical repair-knowledge population**. Building a one-off Civic-specific publisher would create the vehicle-specific architecture PartGraph is designed to avoid.

Until that generic operator ingestion/publication orchestrator exists, this runbook and the machine-readable plan are the authoritative persistent-publication contract. A future executor must consume reviewed data generically, enforce the same evidence/claim/materializer boundaries, and must not encode special-case logic for this reference vehicle.

Production publication remains unauthorized by this document.
