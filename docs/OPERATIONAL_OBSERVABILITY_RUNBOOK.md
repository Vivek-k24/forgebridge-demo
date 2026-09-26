# PartGraph Operational Observability and SLO Runbook

Status: REL-007 implementation control. This runbook does not authorize PR #84 merge, production migration, provider activation, canonical publication, or production cutover.

## Purpose

PartGraph must let an operator answer three questions quickly when the service is unhealthy:

1. What broke?
2. Where did it break?
3. Since when has it been broken?

The MVP deliberately avoids introducing a separate Prometheus/Grafana/Tempo stack. The current hosted backend is Vercel native request/runtime observability, supplemented by PartGraph structured runtime events using schema `partgraph.observability.v1`. The event schema uses stable OpenTelemetry-style field names and W3C `traceparent` correlation so a future OTLP-capable backend can be attached without rewriting the business call sites.

The versioned SLO and alert contract is `ops/observability/slo_v1.json`.

## Current backend and alert-delivery status

The connected `partgraph-main` Vercel project is currently on the Hobby plan.

Available now:

- Vercel request status/duration observability;
- Vercel runtime logs;
- Vercel runtime-error grouping;
- PartGraph request IDs;
- PartGraph W3C trace IDs/span IDs in structured application events;
- database readiness events;
- provider-ingestion outcome events;
- photo-storage reconciliation outcome events.

Not available on the current plan as an active production control:

- Vercel Observability Plus custom/anomaly alert delivery;
- Vercel log/trace Drains to an external backend.

Therefore the alert definitions in `ops/observability/slo_v1.json` are **defined but not yet active**. REL-007 must not be represented as fully production-remediated until an alert-capable backend is connected or the hosting plan supplies equivalent alert delivery and the rules are activated and tested.

A fresh Phase 10 capability review on 2026-09-20 confirmed this is now an external integration/capability decision rather than missing application instrumentation. Vercel's current observability guidance states that Drains require Pro or Enterprise. The repository contains no `VERCEL_TOKEN`/drain automation and no configured external monitoring backend. The connected toolset exposes runtime-log inspection but no alert/drain-management action. The machine-readable boundary is `ops/observability/alert_delivery_capability_v1.json`.

Do not add a repository-only "alert" that merely writes another log line or checks one health endpoint and claim REL-007 complete. The existing alert catalog covers request availability/latency, mutation errors, database readiness, provider ingestion, and media reconciliation; completion requires real notification delivery for those signal classes.

This limitation is separate from `PG-AUD-REL-001`, where Neon production backup/branch-protection controls are also still plan-blocked.

## Structured telemetry contract

Every PartGraph application event is emitted as one JSON object. Required fields are:

- `schema`: `partgraph.observability.v1`
- `timestamp`: UTC timestamp
- `service.name`: `partgraph-api`
- `deployment.environment`: local, preview, or production environment label
- `event.name`: stable event identifier
- `severity`: logging severity
- `trace_id`: 32 lowercase hexadecimal characters
- `span_id`: 16 lowercase hexadecimal characters
- `request.id`: present when the event belongs to an HTTP request

HTTP requests accept a valid W3C `traceparent` header. PartGraph preserves the upstream trace ID, creates a new local span ID, and returns a current `traceparent` response header. Invalid trace headers are ignored and replaced with a fresh trace context.

Do not add VINs, session cookies, authorization headers, CSRF tokens, provider credentials, uploaded photo bytes, free-form user text, or database connection strings to observability events.

## Stable event names

### `http.server.request`

One completion event for each API response. Important attributes:

- `http.request.method`
- `http.route`
- `http.response.status_code`
- `server.duration_ms`
- `partgraph.request.is_mutation`

Use the route template rather than concrete user/session UUID paths whenever the framework exposes the matched route.

### `error.unhandled`

Emitted beside the existing exception traceback for an unexpected server exception. Important attributes:

- `exception.type`
- `http.request.method`
- `http.route`

The structured event intentionally does not serialize the exception message because exceptions can contain database/provider details.

### `database.readiness`

Emitted by the database readiness probe. Important attributes:

- `outcome`: `success` or `failure`
- `database.duration_ms` on success
- `exception.type` on failure

### `provider.ingestion`

Emitted for synchronous operator-triggered provider acquisition/staging. Important attributes:

- `provider.name`
- `partgraph.ingestion.mode`
- `stage`
- `outcome`
- candidate/insert counts on success
- `exception.type` on failure

No provider credential or raw provider payload is logged.

### `media.reconciliation.item`

Emitted when one durable photo-storage row is reconciled. Important attributes:

- `outcome`
- `partgraph.media.operation`
- `partgraph.media.storage_attempt`
- `partgraph.photo_id`
- `exception.type` only on failure

### `media.reconciliation.batch`

Emitted once per reconciliation batch with ready/deleted/failed/no-op counts. A non-zero failed count is an operational failure signal even when the durable row remains safely retryable.

## Initial service level objectives

The values below are intentionally modest MVP objectives. Revisit them after real production traffic exists; do not tighten them merely for appearances.

- API availability: at least 99.5% non-5xx API requests over a rolling 30-day window.
- API latency: p95 server duration at or below 2.5 seconds over a rolling 7-day window.
- Mutation server-error rate: no more than 1.0% 5xx responses for POST/PUT/PATCH/DELETE API requests over a rolling 30-day window.
- Database readiness: at least 99.9% successful readiness checks over a rolling 30-day window.
- Provider ingestion: no uninvestigated `operator_sync` provider-ingestion failure.
- Media reconciliation: at least 99% of durable photo-storage work finalizes without a failed reconciliation attempt and no failed batch remains uninvestigated.

These are operational objectives, not contractual customer SLAs.

## Incident correlation procedure

When investigating an API incident:

1. Identify the first failing request or grouped Vercel runtime error and record its timestamp, deployment, route, status, and PartGraph `request.id` when present.
2. Search structured logs for the same `request.id`; if unavailable, use `trace_id` and the narrowest matching time range.
3. Compare the failing deployment/reference with the last known-good deployment.
4. Determine the component from `event.name`: HTTP boundary, database, provider ingestion, or media reconciliation.
5. Follow the matching alert procedure below.
6. Do not mutate production data merely to test a hypothesis. Use read-only diagnostics first.
7. Record the incident start time, first observed symptom, affected component, mitigation, and verification evidence.

## Alert procedures

### PG-OBS-API-AVAILABILITY

**Owner:** PartGraph operator  
**Severity:** critical  
**Condition:** more than 2% 5xx responses in 15 minutes with at least 20 API requests, or two consecutive readiness failures.

Actions:

1. Inspect grouped runtime errors for the affected period and routes.
2. Separate database failures from application exceptions and platform/deployment failures.
3. Check `/api/v1/health/live` and `/api/v1/health/ready` independently. A live success plus ready failure points toward database readiness rather than total process failure.
4. Correlate the first failing deployment and commit SHA.
5. If failures began immediately after a deployment, stop further promotion and use the normal rollback/redeploy process; do not alter production schema outside the migration/cutover procedure.
6. Verify recovery with successful readiness responses and a clean runtime-error scan.

### PG-OBS-API-LATENCY

**Owner:** PartGraph operator  
**Severity:** warning  
**Condition:** p95 API server duration above 3 seconds for 15 minutes with at least 20 requests.

Actions:

1. Group by route and identify whether latency is broad or isolated.
2. Search `http.server.request`, `PERF_SLOW_REQUEST`, and `PERF_HARD_BOUNDARY_EXCEEDED` events around the same time.
3. Check database readiness latency and provider-call failures/timeouts before changing request deadlines.
4. Do not increase the API deadline as the first mitigation; the provider/API timeout hierarchy is a deliberate reliability boundary.
5. Re-test the affected route after the root cause is corrected.

### PG-OBS-MUTATION-ERROR-RATE

**Owner:** PartGraph operator  
**Severity:** critical  
**Condition:** more than 2% mutation 5xx responses in 15 minutes with at least 10 mutation requests.

Actions:

1. Filter `http.server.request` to `partgraph.request.is_mutation=true` and 5xx status.
2. Correlate `request.id` and `trace_id` with unexpected-error events.
3. Determine whether the write outcome is known. Never blindly replay a request when the client or server cannot prove whether the mutation committed.
4. Use the existing authoritative write-recovery endpoints for ambiguous repair mutations.
5. Verify idempotency behavior before any manual retry.

### PG-OBS-DATABASE-READINESS

**Owner:** PartGraph operator  
**Severity:** critical  
**Condition:** two consecutive readiness failures or any `database.readiness` event with `outcome=failure`.

Actions:

1. Confirm `/api/v1/health/live` separately from `/api/v1/health/ready`.
2. Inspect `database.readiness` and grouped runtime errors for connection invalidation, TLS/SSL closure, connection-limit, timeout, or SQL failures.
3. Check Neon project/branch health and connection settings read-only.
4. On Vercel, preserve the serverless `NullPool` strategy; do not enable retained per-instance SQLAlchemy pooling as an emergency workaround.
5. After recovery, require repeated successful readiness checks before declaring the incident resolved.

### PG-OBS-PROVIDER-INGESTION

**Owner:** PartGraph operator  
**Severity:** warning  
**Condition:** any `provider.ingestion` event with `outcome=failure`.

Actions:

1. Record `stage`, provider name, request ID, trace ID, and timestamp.
2. Determine whether the failure occurred during acquisition, source-governance validation, or staging.
3. Re-check provider/source enabled state, source automation permission, provider/source binding, and the fixed trusted NHTSA endpoint contract.
4. Do not enable scheduled/continuous/bulk/worker ingestion to work around a synchronous failure.
5. Retry only after the failure cause is understood; canonical publication remains a separate reviewed action.

### PG-OBS-MEDIA-RECONCILIATION

**Owner:** PartGraph operator  
**Severity:** critical  
**Condition:** any reconciliation batch reports `failed_count>0`, or the same durable photo item repeatedly emits `outcome=failure`.

Actions:

1. Identify the durable `partgraph.photo_id`, operation, attempt number, and exception type.
2. Inspect the database row state and `storage_error` read-only before touching storage.
3. Preserve the database-first outbox contract: do not mark a photo ready/deleted manually merely because a file operation appears to have succeeded.
4. Re-run the authorized reconciliation path after the storage problem is corrected. The operation is designed to be idempotent.
5. Confirm a subsequent item/batch event reaches `ready` or `deleted` with no failed count.

### PG-OBS-BACKUP-PROTECTION

**Owner:** PartGraph operator  
**Severity:** critical production-cutover gate  
**Condition:** production branch protection, automatic daily backup protection, or required retention is absent.

Actions:

1. Follow `docs/DISASTER_RECOVERY_RUNBOOK.md`.
2. Treat the current Neon plan limitations recorded there as unresolved; observability does not substitute for backups.
3. Do not cut over PR #84 while the required backup/protection controls remain absent unless an explicitly approved equivalent recovery design replaces them.
4. After the plan/control changes, repeat the recovery drill and verify backup/retention status before changing this gate.

## Alert activation gate

Before REL-007 can be marked fully remediated, activate and test the alert catalog in one supported backend. The current capability boundary is recorded in `ops/observability/alert_delivery_capability_v1.json`. Acceptable paths are:

- Vercel Observability Plus/custom alerts with rules matching `ops/observability/slo_v1.json`; or
- an external error/metrics/OTLP-capable backend receiving the PartGraph/Vercel telemetry with equivalent rules.

Activation proof must record:

- backend name;
- rule IDs mapped to all `PG-OBS-*` definitions;
- notification destination ownership;
- one safe test alert or equivalent rule-validation proof per signal class;
- timestamp and deployment/environment used for validation.

Do not place backend tokens, DSNs, webhook secrets, or drain signing secrets in the repository.
