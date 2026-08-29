# PartGraph system UML

This document is the living visual map of the PartGraph product and architecture. It is not a sprint board or a second source of execution truth. GitHub issues and pull requests define implementation status; this document explains how the pieces connect from vehicle identification through repair readiness, guided repair, resume, procurement, and future AI assistance.

## Product invariant: broad vehicle coverage

PartGraph is not a Honda-specific application. Honda and the 2009 Civic Hybrid are a real-world validation case. Canonical repair truth is always scoped by `VehicleConfiguration`, so the same architecture supports every manufacturer, model, trim, engine, transmission, drivetrain, body style, market, and model year represented by the supported vehicle taxonomy when verified repair data exists for that exact configuration.

Current market boundary is US and Canada, model years 1996 through the current calendar year, subject to the controlled manufacturer policy in the vehicle-identity domain.

A repair definition for one vehicle configuration must never leak into another configuration merely because names look similar.

## 1. End-to-end product flow

```mermaid
flowchart TD
    U[Owner] --> AUTH[Register / Sign in]
    AUTH --> GARAGE[Garage]
    GARAGE --> IDENTIFY{Vehicle identification}
    IDENTIFY -->|Manual selector| SELECT[Canonical vehicle resolver]
    IDENTIFY -->|VIN| VIN[NHTSA identity evidence + resolver]
    SELECT --> UV[UserVehicle]
    VIN --> UV

    UV --> RS[Repair Session]
    RS --> BIND{Exact verified RepairDefinition available?}
    BIND -->|No| MANUAL[Manual/temporary repair memory only]
    BIND -->|Yes| RD[Verified RepairDefinition]

    RD --> MANIFEST[Deterministic requirement manifest]
    MANIFEST --> READY[Inventory / readiness]
    READY --> HAVE{Ready to perform repair?}
    HAVE -->|Missing items| PROCURE[Procurement candidates]
    PROCURE --> READY
    HAVE -->|Ready| PROCEDURE[Verified procedure guidance]

    PROCEDURE --> ACTION[Current verified action]
    ACTION --> OBSERVE[Physical work + observations/photos/exceptions]
    OBSERVE --> STATE[Append-only RepairSession events + projections]
    STATE --> DONE{Repair complete?}
    DONE -->|No / pause| RESUME[Resume / reorientation]
    RESUME --> READY
    RESUME --> ACTION
    DONE -->|Yes| ARCHIVE[Archive completed RepairSession]

    RD -. provenance .-> CLAIMS[Verified mechanical claims]
    CLAIMS -. evidence .-> SOURCES[Source records / OEM / licensed evidence]
    OBSERVE -. future assist .-> AI[AI proposes explanation/observation only]
    AI -. candidate only .-> OBSERVE
```

## 2. Canonical truth versus private owner state

```mermaid
classDiagram
    class VehicleConfiguration {
      +UUID id
      +year
      +market
      +make
      +model
      +generation?
      +trim?
      +body_style?
      +engine?
      +transmission?
      +drivetrain?
    }

    class User {
      +UUID id
    }

    class UserVehicle {
      +UUID id
      +UUID user_id
      +UUID canonical_configuration_id?
      +identity_snapshot
      +encrypted_vin?
    }

    class RepairDefinition {
      +UUID id
      +UUID vehicle_configuration_id
      +repair_key
      +version
      +status
    }

    class RepairOperation {
      +UUID id
      +position
      +operation_key
    }

    class RequirementDefinition {
      +UUID id
      +requirement_key
      +category
      +display_name
    }

    class RequirementUse {
      +UUID id
      +quantity?
      +unit?
      +necessity
      +fulfillment_mode
      +timing
    }

    class MechanicalClaim {
      +UUID id
      +claim_domain
      +repair_key?
      +exact_applicability
      +promotion_state
    }

    class RequirementUseEvidence {
      +UUID requirement_use_id
      +UUID mechanical_claim_id
    }

    class RepairSession {
      +UUID id
      +UUID user_id
      +UUID user_vehicle_id
      +UUID repair_definition_id?
      +title
    }

    class UserGarageInventoryItem {
      +UUID id
      +UUID user_id
      +UUID requirement_definition_id
      +quantity_available
    }

    class RepairRequirementState {
      +UUID id
      +UUID user_id
      +UUID session_id
      +UUID requirement_use_id
      +readiness_state
      +quantity_available
    }

    User "1" --> "many" UserVehicle : owns
    VehicleConfiguration "1" <-- "many" UserVehicle : may resolve to
    VehicleConfiguration "1" --> "many" RepairDefinition : exact applicability
    RepairDefinition "1" --> "many" RepairOperation
    RepairDefinition "1" --> "many" RequirementUse
    RepairOperation "0..1" <-- "many" RequirementUse : operation scope
    RequirementDefinition "1" <-- "many" RequirementUse
    RequirementUse "1" --> "many" RequirementUseEvidence
    MechanicalClaim "1" <-- "many" RequirementUseEvidence
    UserVehicle "1" --> "many" RepairSession
    RepairDefinition "0..1" <-- "many" RepairSession : explicit binding
    User "1" --> "many" UserGarageInventoryItem
    RequirementDefinition "1" <-- "many" UserGarageInventoryItem
    RepairSession "1" --> "many" RepairRequirementState
    RequirementUse "1" <-- "many" RepairRequirementState
```

The key boundary is deliberate:

- `VehicleConfiguration`, `RepairDefinition`, `RequirementDefinition`, `RequirementUse`, and verified claims are shared canonical truth.
- `UserVehicle`, `RepairSession`, garage inventory, readiness state, observations, photos, and physical repair memory are private owner state protected by authorization and PostgreSQL row-level security where applicable.

## 3. Manufacturer/model/trim applicability mapping

```mermaid
flowchart LR
    TAX[Supported vehicle taxonomy] --> VC1[VehicleConfiguration A]
    TAX --> VC2[VehicleConfiguration B]
    TAX --> VC3[VehicleConfiguration C]

    VC1 --> R1[RepairDefinition: repair_key X]
    VC2 --> R2[RepairDefinition: repair_key X]
    VC3 --> R3[RepairDefinition: repair_key Y]

    R1 --> M1[Manifest A]
    R2 --> M2[Manifest B]
    R3 --> M3[Manifest C]

    M1 -. protected by exact applicability .-> GUARD[No cross-configuration fallback]
    M2 -. protected by exact applicability .-> GUARD
    M3 -. protected by exact applicability .-> GUARD
```

A shared `repair_key` identifies the type of repair; it does **not** make requirements interchangeable across vehicles. The canonical lookup key is effectively:

`exact VehicleConfiguration + repair_key + verified/current definition version`

This is what prevents a Honda requirement, Toyota requirement, or even a different Civic trim/engine requirement from being reused merely because the repair name is the same.

## 4. Evidence-to-canonical-truth pipeline

```mermaid
flowchart LR
    SRC[Source / provider] --> RECORD[Source record]
    RECORD --> EXTRACT[Extracted claim]
    EXTRACT --> NORMALIZE[Normalized candidate]
    NORMALIZE --> VALIDATE[Applicability + conflict validation]
    VALIDATE --> REVIEW{Review / promotion}
    REVIEW -->|verified| CLAIM[MechanicalClaim]
    REVIEW -->|needs review| HOLD[Needs review]
    REVIEW -->|conflict| CONFLICT[Explicit conflict]
    REVIEW -->|rejected| REJECT[Rejected]
    CLAIM --> LINK[RequirementUseEvidence]
    LINK --> USE[RequirementUse]
    USE --> MANIFEST[Verified manifest]

    RETAIL[Retailer / marketplace] -. procurement only .-> BUY[Product candidate]
    RETAIL -. blocked from canonical promotion .-> PROMOTION_GUARD[Canonical promotion boundary]
    COMMUNITY[Community / video / forum] -. discovery/support only .-> EXTRACT
```

No collector, parser, retailer, community source, or AI model writes canonical mechanical truth directly.

## 5. Repair-readiness reconciliation loop

```mermaid
sequenceDiagram
    participant Owner
    participant Web
    participant API
    participant Canonical as Canonical repair truth
    participant Private as Private readiness / garage state
    participant Session as RepairSession history

    Owner->>Web: Open Inventory for repair
    Web->>API: Load bound repair readiness
    API->>Canonical: Load exact verified definition + requirements
    Canonical-->>API: Aggregated manifest
    API->>Private: Load reusable garage inventory + session overrides
    Private-->>API: Have / missing / ordered / unavailable quantities
    API-->>Web: One readiness view

    Owner->>Web: Mark requirement Have / Missing / Ordered / Unavailable
    Web->>API: Idempotent readiness mutation
    API->>Session: Validate owner + active edit lease
    API->>Private: Reconcile manifest-level state
    API->>Session: Append domain event
    API-->>Web: Updated readiness summary

    Note over API,Private: Reusable requirements are reconciled once at manifest level even when several operations reference the same RequirementUse capability.
```

## 6. Pause/resume loop

```mermaid
stateDiagram-v2
    [*] --> Active
    Active --> Paused: pause
    Paused --> Active: resume
    Active --> Archived: repair complete/archive
    Paused --> Archived: archive

    state Active {
      [*] --> Readiness
      Readiness --> GuidedAction: requirements ready
      GuidedAction --> Observation: physical work
      Observation --> GuidedAction: continue
      Observation --> Readiness: newly discovered blocker
    }

    Paused --> Reorientation: reopen later
    Reorientation --> Active: restore current physical/verified state
    Archived --> [*]
```

## 7. Service/component architecture

```mermaid
flowchart TB
    BROWSER[React / TypeScript web] -->|HTTPS / JSON| API[FastAPI modular monolith]
    API --> PG[(PostgreSQL authoritative state)]
    API --> MEDIA[Private photo storage adapter]
    API -->|user initiated VIN only| NHTSA[NHTSA vPIC]

    COLLECTOR[Future collector service] -->|staging-only DB role| STAGING[(catalog_staging)]
    STAGING --> PROMOTE[Explicit review/promotion]
    PROMOTE --> PG

    AI[Future AI/ML services] -. optional candidate/explanation .-> API
    AI -. never authoritative state .-> AI_GUARD[Candidate-only boundary]

    CI[GitHub Actions] --> TEST[Tests / migrations / security / containers]
    TEST --> GHCR[GHCR tested images]
    MAIN[GitHub main] --> PAGES[GitHub Pages static UI preview]
```

The future collector is intentionally separate from the interactive repair path. GitHub Pages is only a static frontend preview; a full public application still requires runtime hosting for FastAPI and PostgreSQL.

## 8. Block dependency map

```mermaid
flowchart LR
    B2[Block 2 Vehicle identity] --> B4[Block 4 Auth/isolation]
    B4 --> B5[Block 5 UserVehicle/VIN]
    B2 --> B3[Block 3 Catalog staging boundary]
    B5 --> B7[Block 7 RepairSession]
    B7 --> B8[Block 8 Repair memory]
    B8 --> B9[Block 9 Resume]
    B3 --> B10[Block 10 Verified requirements/readiness]
    B5 --> B10
    B7 --> B10
    B10 --> B11[Block 11 Verified procedure + safety]
    B9 --> B11
    B11 --> B12[Block 12 AI/ranking assistance]
    B3 -. activate only when approved real ingestion exists .-> B6[Block 6 Collector]
    B6 -. supplies staged evidence .-> B10
```

Collector implementation is deliberately deferred until there is an approved real source to ingest. It is not a reason to block deterministic canonical/readiness architecture.

## 9. Block 10 sub-block map

```mermaid
flowchart LR
    S1[10A Source authority + provenance policy] --> S2[10B Canonical repair/requirement schema]
    S2 --> S3[10C Deterministic manifest aggregation]
    S3 --> S4[10D Verified manifest read API]
    S4 --> S5[10E Explicit RepairSession binding]
    S5 --> S6[10F Private readiness + garage reconciliation]
    S6 --> S7[10G Inventory UI integration]
    S7 --> S8[10H RLS/adversarial/Compose/local validation]
```

Sub-blocks are explanatory implementation structure, not Scrum stories. A sub-block can remain inside the same issue/PR unless isolation materially improves review, testing, or rollback safety.

## 10. Non-negotiable truth rules

1. Vehicle applicability is exact and explicit; similarity is not fitment.
2. Honda is a validation case, not an architectural special case.
3. Repair requirements belong to repair definitions/operations, not globally to a part.
4. Canonical mechanical truth is separate from private user state.
5. Retailer links are procurement candidates after fitment/specification truth exists.
6. AI may propose, rank, explain, or summarize; it does not silently create mechanical truth.
7. Unknown stays unknown; conflicts stay explicit.
8. Core readiness/resume/next-action paths do not depend on collectors or AI being online.
9. Ordinary users should reconcile a requirement once, not maintain duplicate operation-level bookkeeping.
10. Safety/capability policy may restrict guided procedures even when informational repair data exists.
