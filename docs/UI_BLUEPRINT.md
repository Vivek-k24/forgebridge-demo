# PartGraph UI Blueprint

This branch is a living product blueprint for the PartGraph user experience. It is intentionally separate from the production block sequence so the complete repair flow remains visible while backend capabilities are implemented incrementally.

## Product center

PartGraph is not a vehicle lookup tool and not a repair chatbot. The central object is the **Repair Session**.

A user should be able to begin work, remove parts and fasteners, pause for hours or weeks, return later, and recover the same physical context: same vehicle, same repair, same step, same changed parts, same stored fasteners, same blockers, and the next verified safe action.

The product loop is:

`understand -> plan -> act -> observe -> remember -> adapt -> continue`

## UI rule

The blueprint must never fabricate domain records to make a screen look populated.

- Existing backend endpoints may feed real data into the blueprint.
- A future screen may define the data capability it needs.
- Until the backend contract exists, its endpoint path remains `null`.
- Pending screens show an explicit contract-empty state instead of sample vehicles, repair steps, parts, fasteners, photos, inventory, or history.
- Browser-local state may be used only for presentation preferences such as which real saved vehicle is selected.
- Mechanical truth, repair state, private vehicle data, and durable history remain server-authoritative.

The contract registry lives in `web/src/blueprint/contracts.ts`.

## Screen map

### Resume

The primary home surface. It should eventually answer: which vehicle is being repaired, which repair session is active, where the user stopped, what changed, what is blocking progress, and what the next verified action is.

### Garage

Private `UserVehicle` records, VIN-assisted identification, and manual vehicle identity. A private observed vehicle is distinct from shared canonical vehicle truth.

### Repair Session

Verified repair plan, dependencies, current step, prerequisites, blockers, completion state, and next safe action. This is the central working surface.

### Assembly

Canonical assembly structure beside actual observed physical state. Removed, installed, damaged, replaced, missing, and uncertain state must remain explicit.

### Parts

Repair-relevant parts, identity, fitment evidence, condition, and current installation state. Seller data does not override verified fitment.

### Fasteners

Fasteners and small parts removed during the repair, their counts, physical storage locations, origin, and reinstall state.

### Evidence

Photos and structured observations linked to vehicle/session/assembly state. AI may propose structured observations; it does not silently mutate safety-critical truth.

### Inventory

Parts readiness and procurement state. Physical condition and procurement status are separate dimensions.

### History

Append-only repair events, checkpoints, and the information needed to reconstruct and resume a repair.

### Blueprint Map

Developer-facing view of which UI data contracts are already bound to real endpoints and which remain intentionally unbound.

## Integration strategy

Do not plan one giant future merge of this branch.

1. Production work continues in normal product blocks.
2. When a backend capability becomes real, its matching UI slice can be lifted from the blueprint into that block.
3. The blueprint is then rebased or refreshed so it continues to represent the complete product.
4. Once most capabilities are real, the remaining shell/navigation can be merged normally.

This keeps the blueprint useful without allowing prototype structure to dictate backend architecture.

## Current real contracts

At the time this blueprint was created, private garage, VIN identification, and canonical vehicle-selection APIs are already real. Repair Session, assembly state, parts state, fastener memory, evidence, inventory, and session-history contracts remain deliberately unbound until their backend blocks define them.
