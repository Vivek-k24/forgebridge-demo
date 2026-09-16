# Provider Ingestion Scale Gate

## Current supported execution mode

PartGraph currently supports exactly one provider-ingestion execution mode:

`operator_sync`

In this mode, an authenticated operator explicitly starts one bounded ingestion request through the operator API. The request fetches, validates, stages, commits, and returns synchronously. Provider enablement, source approval, `automation_allowed`, and provider/source binding enablement are eligibility/governance controls only. None of them schedules polling or starts continuous ingestion.

The environment variable `PARTGRAPH_PROVIDER_INGESTION_MODE` therefore accepts only `operator_sync`. Any other value fails application configuration at startup.

This restriction is intentional. The current MVP does not have a durable ingestion queue, bounded worker fleet, retry scheduler, provider-rate limiter, or dead-letter state. Adding a scheduler or bulk/continuous mode on top of the synchronous request path would create uncontrolled concurrency and retry pressure rather than real backpressure.

## What must exist before another mode can be enabled

A future scheduled, continuous, bulk, or worker-based provider mode must not be added by changing the environment variable allowlist alone. The implementation and release review must include all of the following:

- a durable job record or queue whose state survives process/serverless restarts;
- deterministic/idempotent job and ingestion-batch keys so retries cannot duplicate intent;
- a bounded worker concurrency model with an explicit maximum number of simultaneous provider requests;
- per-provider rate limits and concurrency limits;
- exponential retry backoff with jitter and a finite retry budget;
- terminal failure/dead-letter state that requires explicit retry or operator disposition;
- lease/claim semantics so two workers cannot execute the same job concurrently;
- operator visibility into queued, running, retrying, failed, cancelled, and completed jobs;
- cancellation/shutdown behavior that does not silently lose claimed work;
- metrics for queue depth, job age, provider latency/failure rate, retry count, and terminal failures;
- load tests demonstrating bounded provider concurrency and bounded database connection/write pressure;
- an updated production runbook that defines capacity, alert thresholds, recovery, and rollback.

Only after those controls exist should `SUPPORTED_PROVIDER_INGESTION_MODES` gain another value.

## Current route boundary

The external-provider MVP path is intentionally narrow:

- `POST /api/v1/operator/nhtsa/recalls/stage` is operator-authenticated and synchronous.
- Reviewed reference-data staging is also operator-triggered and synchronous; it does not create an external polling mechanism.
- No Vercel cron is allowed to invoke provider ingestion.
- No public/user-facing provider-ingestion endpoint exists.

Permanent CI checks the startup mode allowlist and verifies that production code does not acquire a second caller of the synchronous staging entry points. This is a scale-safety gate, not a substitute for the durable queue design listed above.
