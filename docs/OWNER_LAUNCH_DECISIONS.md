# PartGraph Owner Launch Decision Packet

Status: **owner/admin decisions pending. No Production authorization is implied.**

Machine-readable source: `ops/cutover/phase10_owner_decisions_v1.json`

## Why this packet exists

The MVP engineering work and decision-free remediation are complete at the current boundary. The remaining launch work is no longer a list of bugs. It is a short set of owner/infrastructure decisions plus activation evidence.

Use this document instead of reopening completed Phase 0–9 remediation work.

## Recommended default decisions

These are **recommendations, not approvals**. No subscription, repository setting, Vercel protection setting, database configuration, PR state, or Production resource changes because this section exists.

### Database protection: recommend Neon Scale

Use Neon **Scale** for the Production project, enable protection on the Production branch, and start with a **7-day restore window**.

Why this is the default recommendation:

- the current Free project cannot create the required automatic backup schedule;
- protected branches are a Scale capability;
- Scale supports longer point-in-time restore history;
- keeping backup/protection inside Neon avoids introducing and operating a second backup system;
- seven days meets the current MVP recovery target without retaining more history than required initially.

This is preferable to upgrading only far enough to gain longer restore history while still lacking the prepared branch-protection objective.

### Human alert delivery: recommend Vercel Pro + Datadog Log Drain

Upgrade the existing Vercel team to **Pro**, then connect a **Datadog Log Drain** for PartGraph.

Why:

- PartGraph already emits the required structured runtime signals;
- Vercel Pro enables Log Drains;
- Datadog's Vercel integration can ingest function logs and create custom metrics/alerts from them;
- this covers PartGraph-specific database-readiness, provider-ingestion, media-reconciliation, request, and error signals without adding new application instrumentation.

Vercel native anomaly alerts remain useful as an optional secondary layer, but they are not the primary recommendation because the current native alert types do not by themselves prove all PartGraph-specific PG-OBS signals.

An external backend remains valid later if the product needs deeper application-performance monitoring or cross-provider incident management.

### GitHub main protection: recommend approve

Apply the already-tested `ops/cutover/phase10_branch_governance_v1.json` policy to `main`.

The policy deliberately keeps required approvals at zero for the current solo-maintainer workflow while requiring the stable `MVP merge gate`.

### Cutover traffic freeze: recommend approve for cutover only

Use the already-selected **Vercel Authentication → All Deployments** barrier during the authorized cutover window. Do not enable it now.

### Final Production authorization: recommend only after GO

Do not issue standing authorization. Approve one exact candidate only after the refreshed Phase 10 preflight reports **GO**.

### NHTSA proof: recommend defer from launch

Do not hold the MVP launch for the remaining stateful NHTSA operator POST proof. The provider/configuration path is complete and the proof can be collected later when a legitimate browser/HTTP operator execution surface is available.

## Decision 1 — Production database protection

**Audit:** `PG-AUD-REL-001`  
**Required before Production cutover:** yes.

Current state:

- Production restore mechanics are proven.
- Current Neon project history retention is six hours.
- Automatic snapshot scheduling was rejected in a non-production capability probe.
- Branch protection was rejected by the current-plan protected-branch limit.
- Production itself was not changed.

Choose one path:

1. **Neon capability/plan path.** Move the project to a capability set that supports the approved backup/protection target, then configure and verify it.
2. **Equivalent external backup path.** Approve and implement another durable backup/protection design that meets the same recovery objectives.

Do not call REL-001 complete until Production protection is actually configured and fresh recovery evidence is recorded.

## Decision 2 — Human alert delivery

**Audit:** `PG-AUD-REL-007`  
**Required before Production cutover:** explicit disposition required.

Application telemetry is already complete. PartGraph emits the required request/error, database-readiness, provider-ingestion, and media-reconciliation signals.

Choose one disposition:

1. activate an eligible native/Vercel alert capability;
2. connect an external alert backend and map the existing PG-OBS rules; or
3. explicitly accept the temporary launch risk and document a manual monitoring procedure.

Do not add fake "alerting" that only creates another log message.

## Decision 3 — Protect GitHub main

**Audit:** `PG-AUD-DEP-003`  
**Required before Production cutover:** explicit disposition required.

The prepared policy is `ops/cutover/phase10_branch_governance_v1.json`.

It requires:

- pull requests for `main`;
- zero mandatory human approvals for the current solo-maintainer workflow;
- `MVP merge gate` required;
- branch up to date;
- review conversations resolved;
- force pushes/deletions blocked.

The policy has been tested in CI, but `main` is still unprotected because the connected GitHub App lacks repository Administration permission.

## Decision 4 — Activate the cutover traffic barrier

**Audit:** `PG-AUD-DEP-005`  
**Required before Production cutover:** yes, during the approved cutover window.

Selected control: **Vercel Authentication → All Deployments**.

Do not enable it early. During cutover:

1. capture the existing protection configuration;
2. stage the candidate without Production-domain traffic;
3. enable All Deployments protection;
4. prove anonymous Production traffic is blocked;
5. prove the operator can still reach PartGraph health endpoints;
6. migrate/verify while traffic remains blocked;
7. promote/verify the exact candidate;
8. restore the exact prior protection configuration.

## Decision 5 — Authorize Production

**Audit:** `PG-AUD-DEP-001`  
**Required before Production cutover:** yes.

Only authorize after a fresh Phase 10 preflight reports **GO**.

Authorization must name the exact candidate commit and evidence package. It must not be phrased as a standing authorization for later commits.

## Remaining non-owner proof

### Live NHTSA operator HTTP proof

`PG-AUD-ROAD-002` is not missing implementation.

Preview already contains:

- schema `0063_photo_storage_outbox`;
- an active operator admin;
- enabled NHTSA provider/source/binding configuration.

What is missing is a real authenticated call to:

`POST /api/v1/operator/nhtsa/recalls/stage`

using the real PartGraph operator session and CSRF contract.

This proof may be completed when a legitimate stateful browser/HTTP execution surface is available. Do not weaken authentication merely to close it.

## Not blocking MVP launch

Unless scope changes, the following stay post-MVP/backlog:

- broad canonical repair-knowledge expansion;
- broader accessibility scanning/browser coverage;
- future-scale queue/pooling/outbound-provider hardening;
- broad design-token/cascade cleanup.

## Current engineering conclusion

There are **no decision-free remediation fixes left**.

The product should not be described as Production-ready until the owner/admin choices above are resolved or explicitly dispositioned and the Phase 10 preflight flips from **NO-GO** to **GO**.
