# PartGraph Roadmap

## Current focus: US vehicle identity inventory

PartGraph's current data phase is deliberately narrower than the technical-spec workbench.

Active scope:

- United States market;
- model years 1996 through 2027;
- Acura, Honda, Hyundai, Lexus, Subaru, Toyota;
- year, make, model, trim only.

The goal is to build the broadest source-backed identity universe first. Technical specifications, parts, fluids, procedures, dimensions, performance data, and other vehicle facts remain paused until the identity inventory has been reviewed.

The identity pipeline is union-first:

```text
US make + model year
  -> broad model enumerators
  -> raw source cache + provenance
  -> conservative model-name normalization
  -> trim/style enumerators
  -> conservative trim normalization
  -> source-backed discovered identity
  -> optional independent corroboration
  -> export/review
```

A usable source discovery is retained even when another source does not expose the same row. A second independent source can mark a normalized identity as corroborated. The technical three-source verifier is not used as an admission gate for year/make/model/trim inventory.

The initial identity sources are NHTSA vPIC and FuelEconomy.gov for broad model enumeration, plus KBB and CarsDirect for consumer-facing trim/style enumeration. The source set is extensible and has no architectural maximum.

The collector keeps original source labels and provenance. Normalization removes presentation-only wording such as body-style suffixes where appropriate, while preserving genuine distinctions. Powertrain wording is not automatically treated as a separate model when the evidence shows it is a variant of the base vehicle family.

The earlier 363-row selected-Asian workbook remains a seed/reference batch for later technical work. It is not the current catalog boundary and does not limit the 1996-2027 identity inventory.

Local collection remains separate from Vercel and Neon. Raw captures and PostgreSQL research state stay local until data is deliberately reviewed and published.

## Next gate: identity review

Before technical specification collection resumes:

1. run the six-make identity collector across 1996-2027;
2. export and review make/year/model/trim coverage;
3. identify source-specific gaps and taxonomy anomalies;
4. add targeted identity enumerators where useful;
5. freeze the reviewed identity baseline for the next data phase.

The 2027 model year is inherently moving during 2026, so the inventory can be refreshed as manufacturers and public data sources publish additional 2027 vehicles.

## Later technical profile phase

After the identity baseline is reviewed, PartGraph can resume the field-level technical pipeline:

```text
reviewed vehicle identity
  -> independent technical source collection
  -> immutable raw cache + provenance
  -> source-scoped field extraction
  -> nomenclature/unit normalization
  -> one vote per independent source per field
  -> conflict/authority reconciliation
  -> progressive technical vehicle profile
  -> reviewed canonical publication
```

Ordinary technical facts normally require three independent agreeing sources. There is no fixed source maximum; additional sources can be used whenever evidence is incomplete or conflicting. Manufacturer-authoritative service/fluid facts retain a separate authority boundary.

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

After the current identity phase:

1. resume technical profile collection on the reviewed six-make identity universe;
2. expand source adapters without changing evidence semantics;
3. selectively publish reviewed identity/profile data to the hosted database;
4. broaden identity coverage to additional makes and markets only when explicitly scheduled;
5. grow verified repair definitions, requirements, procedures, and part applicability on exact vehicle configurations;
6. add the planned admin/operations surface;
7. extend the existing API-driven product to mobile clients without duplicating canonical business logic.
