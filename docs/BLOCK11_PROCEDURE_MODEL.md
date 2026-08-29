# Block 11 verified procedure model

This document supplements the living `PARTGRAPH_SYSTEM_UML.md` while Block 11 is active. It describes the procedure/safety structure being implemented; GitHub issue #48 remains the execution source of truth.

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
    class ProcedureActionState

    VehicleConfiguration "1" --> "many" RepairDefinition
    RepairCapabilityPolicy "1" <-- "many" RepairDefinition
    RepairDefinition "1" --> "many" ProcedureAction
    ProcedureAction "many" --> "many" ProcedureAction : prerequisite
    ProcedureAction "1" --> "many" ProcedureActionRequirementUse
    RequirementUse "1" <-- "many" ProcedureActionRequirementUse
    ProcedureAction "1" --> "many" ProcedureActionEvidence
    MechanicalClaim "1" <-- "many" ProcedureActionEvidence
    RepairDefinition "1" <-- "many" RepairSession : version-pinned binding
    RepairSession "1" --> "many" ProcedureActionState : Block 11D
```

`ProcedureActionState` is shown as the next private-state boundary; it is intentionally not part of migration `0012` yet.

## Safety gate and next-action loop

```mermaid
flowchart TD
    RS[RepairSession] --> RD[Version-pinned RepairDefinition]
    RD --> POLICY[RepairCapabilityPolicy]
    POLICY --> STATE{guidance_state}

    STATE -->|prohibited| STOP[No guided procedure]
    STATE -->|professional_required| INFO[Information-only / professional service boundary]
    STATE -->|supported| PLAN[Load exact verified ProcedureActions]

    PLAN --> EVIDENCE{Every action has exact verified repair_procedure evidence?}
    EVIDENCE -->|No| FAIL[Fail closed: canonical integrity error]
    EVIDENCE -->|Yes| GRAPH[Validate dependency graph]
    GRAPH -->|cycle / cross-definition / order conflict| FAIL
    GRAPH -->|valid| PROGRESS[Load private action progress]

    PROGRESS --> ELIGIBLE[Find pending action whose prerequisites are complete]
    ELIGIBLE --> REQUIREMENTS{Linked required RequirementUses ready?}
    REQUIREMENTS -->|No| BLOCKED[Inventory blocker -> readiness]
    REQUIREMENTS -->|Yes| CURRENT[Current verified action]
    CURRENT --> WORK[Owner performs physical work]
    WORK --> RESULT{Result}
    RESULT -->|complete| EVENT[Append progress event]
    RESULT -->|blocked/problem| OBSERVE[Capture blocker/observation]
    EVENT --> PROGRESS
    OBSERVE --> PROGRESS
```

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
