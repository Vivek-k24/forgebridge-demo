# Production knowledge bootstrap

This document records the first approved, real production knowledge insertion for PartGraph.

## Scope

The bootstrap is intentionally limited to **one vehicle-identity record**. It does not create any repair definition, repair operation, requirement, procedure action, torque value, tool size, fluid specification, fitment claim, or safety instruction.

Canonical identity created:

- model year: 2009
- market: US
- make: Honda
- model: Civic
- trim: Hybrid
- engine detail established by this source: inline 4-cylinder hybrid
- transmission: CVT
- body style: unresolved by this bootstrap
- drivetrain: unresolved by this bootstrap
- engine displacement: unresolved by this bootstrap
- generation: unresolved by this bootstrap

PartGraph may later enrich the same identity only when additional qualified evidence explicitly establishes the missing fields and remains compatible with the existing verified identity.

## Source approval record

Provider/source: National Highway Traffic Safety Administration (NHTSA), public investigation record containing a Honda Tech Line vehicle-information entry.

Document ID: `INRD-DP10004-48962P`

Stable source URL: `https://static.nhtsa.gov/odi/inv/2010/INRD-DP10004-48962P.pdf`

Reviewed locator: page 390.

The reviewed record explicitly identifies a 2009 Honda Civic Hybrid, CVT transmission, a four-cylinder hybrid description, Honda engine-number prefix LDA2, and a USA market marker. PartGraph does not infer engine displacement, drivetrain, generation, or a body-style label from that record.

Source class: `government`.

License/status decision: approved for this manually curated public-government identity record only.

Automation decision: **disabled**. This approval does not authorize a collector, scraping, bulk ingestion, or automated retrieval from NHTSA or Honda.

Reviewer/promotion label: `partgraph-production-bootstrap-2026-08-31`.

## Pipeline

The bootstrap preserves the normal evidence boundary rather than inserting an unexplained canonical row:

```text
catalog_staging.ingestion_batches
  -> catalog_staging.source_records
  -> catalog_verified_evidence
  -> mechanical_claims (vehicle_identity)
  -> vehicle_configurations
```

The staging record retains the extracted source fields, provenance locators, deterministic content hash, review state, and the fields deliberately excluded from canonical identity.

## Safety and truth boundary

The source is used only for vehicle identity. It is not treated as authority for a repair workflow merely because the underlying document originated from Honda technical support.

No repair definition is attached to this vehicle by the bootstrap. If a user starts a RepairSession for this configuration before verified repair knowledge exists, PartGraph must continue to fail closed and report that verified guidance is unavailable.

## Why the engine is stored as `I4 HYBRID`

The reviewed record explicitly provides the four-cylinder and hybrid identity but does not establish displacement in the reviewed evidence. The canonical identity therefore stores the narrower verified engine description instead of adding the commonly known 1.3-liter value.

The vehicle-selection compatibility logic intentionally allows richer later input such as `1.3L I4 Hybrid` to match this less-specific verified identity when the supplied structured details are compatible. The additional displacement is not promoted to canonical truth until separately verified.

## Collector gate remains closed

This migration is a curated one-record bootstrap, not Block 10 collection. The standing collection gate in `AGENTS.md` and `docs/REPAIR_DATA_STRATEGY.md` remains unchanged:

- no collector runs from CI, deployment, page load, or a repair session;
- no bulk source is activated by this bootstrap;
- no paid/licensed provider is enabled;
- future collection still requires an explicit source/provider, terms/license review, scope, rate limits, retention rules, collector version, and rollback/failure policy.
