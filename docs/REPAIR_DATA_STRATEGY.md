# PartGraph repair data strategy

PartGraph must know **what a repair requires** before it can tell a DIY user whether they are ready or what to do next. This document defines how repair requirements are sourced, verified, normalized, and mapped without turning retailer listings, community advice, or an LLM into mechanical truth.

## Product questions

A repair workflow should answer three questions:

1. What do I need?
2. How do I do it?
3. Where am I now?

Block 10 owns the first question.

## Core modeling rule

Do not model `part -> tool` as the primary relationship.

A physical part does not inherently require a particular tool. A **repair operation for a specific vehicle configuration** requires tools, parts, fluids, hardware, workspace, and safety prerequisites.

The canonical chain is:

```text
VehicleConfiguration
  -> RepairDefinition
    -> Procedure/Operation
      -> RequirementUse
```

The repair-level readiness manifest is the deterministic union of verified requirement uses.

Example:

```text
2009 Honda Civic Hybrid
  -> radiator replacement
    -> remove upper support hardware
      -> tool requirement: [only if explicitly verified]
      -> hardware requirement: reuse existing / replace if damaged
    -> disconnect cooling hoses
      -> tool/equipment requirements: [only if explicitly verified]
    -> refill and bleed cooling system
      -> fluid + equipment requirements: [only if explicitly verified]
```

A bolt part number, thread size, picture, or retailer listing must never be used to infer a wrench/socket size unless a verified source explicitly establishes that relationship.

## Source hierarchy

### Tier A — Government/open authoritative identity and safety data

Examples:
- NHTSA vPIC: https://vpic.nhtsa.dot.gov/api/
- NHTSA datasets/manufacturer communications: https://www.nhtsa.gov/nhtsa-datasets-and-apis

Use for vehicle identity, recalls, manufacturer communications, safety campaigns, and related context. These are not general repair-procedure or tool-requirement sources.

### Tier B — OEM service information

Examples include manufacturer repair-information portals such as Honda Service Express, Toyota TIS, GM Service Information, Nissan TechInfo, Ford/Motorcraft service information, and equivalent OEM portals.

OEM service information is the preferred authority for explicit procedure-specific facts such as:
- required/special tools
- service specifications
- fluids/capacities
- procedure prerequisites
- replace/reuse instructions
- warnings
- ordered operations

**Licensing and terms are a hard ingestion gate.** Subscription access does not imply permission to scrape, automate, redistribute, or republish the underlying manuals/graphics. For example, Toyota TIS explicitly prohibits data mining and unapproved automated integration. PartGraph must not automate a source until its terms/license permit the intended use.

When permitted, store normalized factual claims and precise provenance/locators. Do not copy whole manuals, diagrams, or large copyrighted passages into the product unless separately licensed.

### Tier C — Licensed OEM-derived structured repair data

This is the preferred scalable route if product licensing is available.

A strong candidate is MOTOR Data as a Service, whose published developer material describes structured service procedures, parts, fluids, specifications, component locations, and other OEM-derived information delivered through web services.

Candidate evaluation must include:
- vehicle/year coverage
- exact content products available
- API/data format
- cost
- rate limits
- attribution requirements
- cache/retention rights
- redistribution/display rights
- whether normalized derived facts may be persisted
- whether use in a public/open-source portfolio product is allowed

No vendor is integrated until those rights are clear.

### Tier D — OEM parts catalogs / licensed parts data

Use for:
- assembly structure
- OEM identifiers
- part quantities
- supersessions
- vehicle applicability

A parts catalog is not a repair procedure. It does not, by itself, establish which tools or operations are required.

### Tier E — Aftermarket data standards

ACES/PIES and their supporting databases are valuable for standardized vehicle/product taxonomy and fitment exchange.

They are standards/reference databases, not a ready-made catalog of which product fits which vehicle. Auto Care explicitly states that application/fitment data still has to be researched, created, or purchased separately.

Use these standards for normalization/interoperability where licensing justifies it, not as mechanical truth by themselves.

### Tier F — Retailers and marketplaces

Examples: OEM retail stores, aftermarket retailers, marketplaces, local stores.

Use only **after** PartGraph has established the required specification/fitment. Retail sources can provide:
- candidate products
- price
- availability
- shipping/pickup
- purchase links

Retail listings never establish canonical mechanical requirements or fitment.

### Tier G — Community/forums/videos

Use for discovery, terminology, common workflow hints, and candidate evidence only.

Community content can help answer questions such as “what do people commonly struggle with?” but it cannot auto-promote a torque value, fitment, fluid, fastener specification, tool size, or procedure step into canonical truth.

## Evidence and claim pipeline

```text
source record
  -> extracted claim
  -> normalized candidate
  -> applicability validation
  -> conflict detection
  -> review/promotion
  -> verified evidence
  -> canonical repair definition / requirement use
```

The existing `catalog_staging` tables remain the raw/staging boundary. A collector writes staging only. Promotion is a separate operation.

Every mechanical claim should retain:
- source/provider
- source class
- document/publication identifier
- URL or stable locator where permitted
- section/page/procedure locator
- published/effective/observed date when available
- exact vehicle applicability
- extraction method/version
- parser confidence
- reviewer/promotion state
- content/reference hash where useful

**Parser confidence is not source authority.** A parser can be 99.9% sure it extracted a sentence from a poor source. That does not make the mechanical claim authoritative.

## Verification policy

- One explicit, exact-applicability OEM or licensed OEM-derived source can be sufficient for a non-safety fact.
- Lower-authority sources require corroboration and/or human review.
- Safety-critical claims and ambiguous applicability require human review initially even when the source is authoritative.
- Conflicts never overwrite existing truth silently; they enter a conflict/review state.
- Retailer/community evidence cannot outrank explicit OEM mechanical information.
- Unsupported inference remains unverified.
- New evidence creates a new version/supersession path rather than mutating historical evidence.

Suggested review states:

```text
staged
needs_review
verified
rejected
conflict
superseded
```

## Requirement model

A canonical requirement use should identify:
- category: tool, equipment, part, fluid, consumable, hardware, workspace, safety prerequisite
- normalized requirement/capability key
- required quantity and unit when applicable
- required vs optional/recommended
- reusable vs consumed
- reuse-existing vs replacement-required
- scope: whole repair, before start, or operation/step
- exact vehicle/repair applicability
- supporting verified-evidence claim IDs

### Why tools attach to operations

If a procedure explicitly says a certain operation uses a 10 mm socket, the tool is linked to that operation. The repair manifest then aggregates that tool once.

If the procedure only says “remove the bolts,” PartGraph must not invent the socket size. The requirement stays unresolved until a qualified source establishes it.

### Hardware semantics

Existing vehicle hardware is not automatically a purchase requirement.

Examples:
- `reuse_existing`: user does not need to buy it unless damaged/missing
- `replace_required`: new hardware is part of readiness
- `replace_if_damaged`: not initially blocking; becomes a shortage if the user reports damage
- `consumed`: clips/seals/one-time items when explicitly established by verified evidence

## User garage and readiness

Canonical truth and private user state remain separate.

```text
Verified Repair Requirements
          |
          v
compare against
          |
          v
Private User Garage Inventory
          |
     +----+----+
     |         |
    HAVE     MISSING / ORDERED / UNAVAILABLE
```

Reusable tools should persist across repairs. If the user already told PartGraph they own a ratchet and a verified required socket, future repairs should pre-fill those capabilities as available.

The initial private readiness states are:
- have
- missing
- ordered
- unavailable

Quantity is tracked where meaningful.

## Procurement boundary

The procurement pipeline is deliberately downstream of repair truth:

```text
verified requirement
  -> verified fitment/specification
  -> retail search
  -> candidate sellers/products
```

Never reverse this flow by turning an Amazon/eBay/retailer listing into mechanical truth.

## Collection policy

No collector runs during CI, deployment, page load, repair-session requests, or ordinary development validation.

Before the first real Block 10 collection/ingestion run, record and approve:
- exact source/provider
- terms/license status
- exact vehicle/repair scope
- expected record types/count range
- rate limits
- storage/retention rules
- collector version
- rollback/failure behavior

Until that approval, Block 10 development uses deterministic fixtures and the already-preserved catalog artifact only where appropriate.