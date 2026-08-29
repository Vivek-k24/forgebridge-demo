# Block 11 verified procedure model

This document supplements the living `PARTGRAPH_SYSTEM_UML.md` while Block 11 is active. It describes the implemented procedure/safety/progress structure; GitHub issue #48 remains the execution source of truth.

## Canonical-to-private mapping

```mermaid
classDiagram
    class VehicleConfiguration
    class RepairDefinition {
      +UUID id
      +UUID vehicle_configuration_id
      +UUID capability_policy_id
      +repair_key
      +version
      +status
    }
    class RepairCapabilityPolicy {
      +policy_key
      +guidance_state
      +rationale
    }
    class ProcedureAction {
      +action_key
      +title
      +instruction
      +warning_text?
      +workspace_note?
      +position
      +skippable
    }
    class ProcedureActionDependency
    class ProcedureActionRequirementUse
    class ProcedureActionEvidence
    class RequirementUse
    class MechanicalClaim {
      +claim_domain = repair_procedure
      +exact_applicability
      +promotion_state
    }
    class RepairSession
    class RepairProcedureActionState {
      +progress_state
      +blocker_code?
      +notes?
    }
    class RepairSessionEvent {
      +event_type = procedure_action_state_changed
      +sequence
    }

    VehicleConfiguration "1" --> "many" RepairDefinition
    RepairCapabilityPolicy "1" <-- "many" RepairDefinition
    RepairDefinition "1" --> "many" ProcedureAction
    ProcedureAction "many" --> "many" ProcedureAction : prerequisite
    ProcedureAction "1" --> "many" ProcedureActionRequirementUse
    RequirementUse "1" <-- "many" ProcedureActionRequirementUse
    ProcedureAction "1" --> "many" ProcedureActionEvidence
    MechanicalClaim "1" <-- "many" ProcedureActionEvidence
    RepairDefinition "1" <-- "many" RepairSession : version-pinned binding
    RepairSession "1" --> "many" RepairProcedureActionState
    ProcedureAction "1" <-- "many" RepairProcedureActionState
    RepairSession "1" --> "many" RepairSessionEvent : append-only history
```

Canonical procedure truth is shared and immutable through verification/versioning. `RepairProcedureActionState` and `RepairSessionEvent` are private owner-scoped state; PostgreSQL row-level security (RLS) isolates them from other users.

## Safety gate and next-action loop

```mermaid
flowchart TD
    RS[RepairSession] --> RD[Version-pinned RepairDefinition]
    RD --> POLICY[RepairCapabilityPolicy]
    POLICY --> STATE{guidance_state}

    STATE -->|prohibited| STOP[No guided procedure]
    STATE -->|professional_required| INFO[Information-only / professional service boundary]
    STATE -->|supported| PLAN[Load exact verified ProcedureActions]

    PLAN --> EVIDENCE{Every action has exact repair_procedure evidence?}
    EVIDENCE -->|No| FAIL[Fail closed: canonical integrity error]
    EVIDENCE -->|Yes| GRAPH[Validate dependency graph]
    GRAPH -->|cycle / cross-definition / order conflict| FAIL
    GRAPH -->|valid| PROGRESS[Load private action progress]

    PROGRESS --> ELIGIBLE[Find first unresolved action whose prerequisites are complete]
    ELIGIBLE --> REQUIREMENTS{Linked required RequirementUses ready?}
    REQUIREMENTS -->|No| INVENTORY[Inventory blocked]
    REQUIREMENTS -->|Yes| CURRENT[Current verified action]
    CURRENT --> WORK[Owner performs physical work]
    WORK --> RESULT{Owner result}
    RESULT -->|complete| COMPLETE[Persist completed]
    RESULT -->|problem| BLOCK[Persist blocked + reason]
    RESULT -->|skip| SKIP{Canonical skippable?}
    SKIP -->|No| REJECT[Reject mutation]
    SKIP -->|Yes| SKIPPED[Persist skipped]
    COMPLETE --> EVENT[Append procedure_action_state_changed]
    BLOCK --> EVENT
    SKIPPED --> EVENT
    EVENT --> PROGRESS
    INVENTORY --> READINESS[Resolve in Inventory]
    READINESS --> PROGRESS
```

The engine does not silently advance past a blocked action. Completion is rejected while an explicitly linked required Inventory item is unresolved. Skip is not a generic user escape hatch; it is valid only when canonical procedure truth explicitly marks that action `skippable`.

## Resume and Guided Repair share one calculation

```mermaid
flowchart LR
    DB[(PostgreSQL)] --> ENGINE[Deterministic guidance service]
    ENGINE --> POLICY[Capability policy]
    ENGINE --> PROC[Verified procedure graph]
    ENGINE --> READY[Repair readiness]
    ENGINE --> STATE[Private action progress]

    POLICY --> NEXT[Current / next verified action]
    PROC --> NEXT
    READY --> NEXT
    STATE --> NEXT

    NEXT --> RESUME[Resume / reorientation]
    NEXT --> GUIDE[Repair session / Guided Repair UI]
    GUIDE --> MUTATE[Complete / problem / verified skip]
    MUTATE --> DB
```

There is no frontend event-history waterfall and no LLM/network/collector dependency in this critical path. A user may change devices and still reconstruct the same server-authoritative repair position.

## Provenance separation

```mermaid
flowchart LR
    REQCLAIM[repair_requirement claim] --> REQUSE[RequirementUse]
    PROCCLAIM[repair_procedure claim] --> ACTION[ProcedureAction]

    REQUSE -. cannot establish instruction .-> GUARD[Domain separation]
    PROCCLAIM -. cannot silently invent requirement .-> GUARD
```

A requirement claim establishes what a repair needs. A procedure claim establishes an explicit action. PartGraph does not use a tool/part requirement as evidence for a mechanical instruction.

## Capability states

```mermaid
stateDiagram-v2
    [*] --> Supported
    [*] --> ProfessionalRequired
    [*] --> Prohibited

    Supported --> GuidedPlan: exact verified procedure exists
    Supported --> NoProcedure: procedure truth incomplete
    ProfessionalRequired --> InformationOnly
    Prohibited --> NoGuidedOutput
```

The capability decision is deterministic database/domain truth and is evaluated before action text is returned. An LLM cannot override this policy.
