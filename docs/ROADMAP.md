# PartGraph Roadmap

## Current focus: vehicle coverage workbench

PartGraph's current data work is the local vehicle research workbench. The first batch contains 363 seed candidates from selected Asian brands for model years 1996-2000. These candidates are a research population, not a complete catalog and not verified merely because they exist.

The collection pipeline is now field-level rather than whole-row matching:

```text
candidate configuration
  -> independent source collection
  -> immutable raw cache + provenance
  -> source-scoped field extraction
  -> nomenclature/unit normalization
  -> one vote per independent source per field
  -> conflict/authority reconciliation
  -> progressive technical vehicle profile
  -> reviewed canonical publication
```

Ordinary technical facts normally need three independent agreeing sources. There is no fixed source maximum; additional sources can be used whenever evidence is incomplete or conflicting. Manufacturer-authoritative service/fluid facts retain a separate authority boundary and are not promoted merely because several generic sites repeat them.

The core technical profile covers vehicle identity, powertrain, transmission, performance, efficiency/emissions, chassis, suspension, steering, brakes, wheels/tires, dimensions/weights/capacities, electrical/charging, safety hardware, and applicable service/fluid specifications. Comfort/convenience equipment is outside the core profile.

Local research remains separate from Vercel and Neon. Raw source material and PostgreSQL workbench state stay local until reviewed data is deliberately published.

## Planned Admin Console

Status: **Draft / not implemented**

A future separate admin surface should cover:

- executive usage overview;
- user/account management;
- product/feature usage;
- catalog collection operations and evidence review;
- AI/model request and token/cost telemetry;
- errors, bugs, reports, and feedback;
- API/database/container health;
- website analytics;
- security/RBAC/audit history;
- future mobile application management.

Admin operational details should remain separate from normal owner-facing repair workflows.

## Future expansion

After the current local research and verification pipeline is proven:

1. expand batch scopes across the supported US/Canada taxonomy;
2. add more independent public/OEM/licensed source adapters without changing field corroboration semantics;
3. publish reviewed canonical/profile evidence to the hosted database;
4. grow verified repair definitions, requirements, procedures, and part applicability on exact vehicle configurations;
5. add the planned admin/operations surface;
6. extend the existing API-driven product to mobile clients without duplicating canonical business logic.
