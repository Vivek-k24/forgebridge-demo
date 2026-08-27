export type ContractStatus = 'bound' | 'pending'

export type BlueprintContract = {
  id: string
  label: string
  status: ContractStatus
  path: string | null
  purpose: string
}

export const BLUEPRINT_CONTRACTS = {
  garage: {
    id: 'garage',
    label: 'Private garage',
    status: 'bound',
    path: '/api/v1/user-vehicles',
    purpose: 'List the authenticated owner’s saved vehicles.',
  },
  vehicleIdentity: {
    id: 'vehicle-identity',
    label: 'Vehicle identity',
    status: 'bound',
    path: '/api/v1/vehicle-selection/resolve',
    purpose: 'Resolve normalized vehicle details against canonical vehicle configurations.',
  },
  vinDecode: {
    id: 'vin-decode',
    label: 'VIN identification',
    status: 'bound',
    path: '/api/v1/user-vehicles/vin/decode',
    purpose: 'Decode a private VIN observation and compare it with canonical vehicle identity.',
  },
  activeRepairSession: {
    id: 'active-repair-session',
    label: 'Active repair session',
    status: 'pending',
    path: null,
    purpose: 'Return the owner’s active repair session and current resumable state.',
  },
  repairPlan: {
    id: 'repair-plan',
    label: 'Repair plan',
    status: 'pending',
    path: null,
    purpose: 'Return verified steps, dependencies, blockers, and the next safe action.',
  },
  assemblyState: {
    id: 'assembly-state',
    label: 'Assembly state',
    status: 'pending',
    path: null,
    purpose: 'Return canonical assembly structure together with observed physical state.',
  },
  partsState: {
    id: 'parts-state',
    label: 'Parts state',
    status: 'pending',
    path: null,
    purpose: 'Return repair-relevant parts, fitment evidence, condition, and installation state.',
  },
  fastenerState: {
    id: 'fastener-state',
    label: 'Fastener memory',
    status: 'pending',
    path: null,
    purpose: 'Return removed fasteners, storage locations, counts, and installation state.',
  },
  evidence: {
    id: 'evidence',
    label: 'Evidence and observations',
    status: 'pending',
    path: null,
    purpose: 'Return photos and structured observations attached to repair state.',
  },
  inventory: {
    id: 'inventory',
    label: 'Inventory and readiness',
    status: 'pending',
    path: null,
    purpose: 'Return required, available, ordered, missing, and installed items.',
  },
  sessionHistory: {
    id: 'session-history',
    label: 'Session history',
    status: 'pending',
    path: null,
    purpose: 'Return append-only repair events and resume checkpoints.',
  },
} satisfies Record<string, BlueprintContract>
