export type PartState = 'need' | 'have' | 'inspect' | 'not-sure';
export type RequirementLevel = 'required' | 'conditional' | 'normally-reusable' | 'single-use' | 'inspect' | 'adjacent-only';
export type RelationshipType =
  | 'mounted_by'
  | 'fastened_by'
  | 'seated_on'
  | 'fluid_connected_to'
  | 'attached_to'
  | 'adjacent_to'
  | 'serviced_with'
  | 'inspect_when_servicing';

export interface VehicleConfig {
  id: string;
  make: 'Honda';
  model: string;
  year: number;
  trim: string;
  body: string;
  engine: string;
  market: string;
  vinRecommended: boolean;
}

export interface SourceClaim {
  label: string;
  status: 'prototype' | 'verified';
  note: string;
  url?: string;
}

export interface PartNode {
  id: string;
  name: string;
  category: 'main' | 'mount' | 'fastener' | 'hose' | 'fan' | 'adjacent' | 'consumable';
  quantity: number;
  requirement: RequirementLevel;
  description: string;
  oemNumber?: string;
  source: SourceClaim;
  diagram: {x: number; y: number; w: number; h: number};
}

export interface PartRelation {
  from: string;
  to: string;
  type: RelationshipType;
  note: string;
}

export const demoVehicle: VehicleConfig = {
  id: 'honda-civic-2009-hybrid-us',
  make: 'Honda',
  model: 'Civic',
  year: 2009,
  trim: 'Hybrid',
  body: 'Sedan',
  engine: '1.3L',
  market: 'US',
  vinRecommended: true,
};

const prototypeSource = (note: string): SourceClaim => ({
  label: 'Prototype relationship',
  status: 'prototype',
  note,
});

export const demoParts: PartNode[] = [
  {
    id: 'radiator',
    name: 'Radiator',
    category: 'main',
    quantity: 1,
    requirement: 'required',
    description: 'Primary repair target for this prototype assembly.',
    source: prototypeSource('OEM identity intentionally left blank until the source ledger verifies exact fitment.'),
    diagram: {x: 325, y: 180, w: 180, h: 190},
  },
  {
    id: 'upper-mount-left',
    name: 'Upper radiator mount — left',
    category: 'mount',
    quantity: 1,
    requirement: 'required',
    description: 'Upper support component. Exact Honda identity must be source-verified before commerce links unlock.',
    source: prototypeSource('Relationship is representative; exact part number and production split are pending verification.'),
    diagram: {x: 300, y: 70, w: 130, h: 60},
  },
  {
    id: 'upper-mount-right',
    name: 'Upper radiator mount — right',
    category: 'mount',
    quantity: 1,
    requirement: 'required',
    description: 'Upper support component. Kept separate because left/right identity may differ by configuration.',
    source: prototypeSource('Exact OEM identity pending verification.'),
    diagram: {x: 455, y: 70, w: 130, h: 60},
  },
  {
    id: 'lower-cushions',
    name: 'Lower radiator cushions',
    category: 'mount',
    quantity: 2,
    requirement: 'required',
    description: 'Lower isolation/support points. Quantity is a prototype assumption until verified against the selected configuration.',
    source: prototypeSource('Quantity and identity must be checked against authoritative Honda data.'),
    diagram: {x: 355, y: 420, w: 120, h: 55},
  },
  {
    id: 'mount-fasteners',
    name: 'Radiator mount fasteners',
    category: 'fastener',
    quantity: 1,
    requirement: 'inspect',
    description: 'Fastener set associated with mounting hardware. The production system must store size, thread, quantity and reuse policy individually.',
    source: prototypeSource('Generic placeholder only. Never use this record as a torque or hardware specification.'),
    diagram: {x: 610, y: 88, w: 130, h: 55},
  },
  {
    id: 'radiator-fan',
    name: 'Radiator fan / shroud assembly',
    category: 'fan',
    quantity: 1,
    requirement: 'inspect',
    description: 'Nearby cooling-air component that may be reused if undamaged and compatible.',
    source: prototypeSource('Exact assembly breakup and OEM numbers pending verification.'),
    diagram: {x: 565, y: 205, w: 170, h: 120},
  },
  {
    id: 'condenser',
    name: 'A/C condenser',
    category: 'adjacent',
    quantity: 1,
    requirement: 'adjacent-only',
    description: 'Adjacent heat exchanger. Included to demonstrate cross-assembly inspection rather than automatic purchase.',
    source: prototypeSource('Adjacency must be verified for each vehicle configuration.'),
    diagram: {x: 80, y: 205, w: 170, h: 120},
  },
  {
    id: 'upper-hose',
    name: 'Upper radiator hose',
    category: 'hose',
    quantity: 1,
    requirement: 'inspect',
    description: 'Cooling-circuit connection. Replace only when condition/service rules require it.',
    source: prototypeSource('Exact routing, clamp type and OEM identity pending verification.'),
    diagram: {x: 92, y: 82, w: 145, h: 55},
  },
  {
    id: 'lower-hose',
    name: 'Lower radiator hose',
    category: 'hose',
    quantity: 1,
    requirement: 'inspect',
    description: 'Cooling-circuit connection. Production data must distinguish routing and clamps by vehicle configuration.',
    source: prototypeSource('Exact routing, clamp type and OEM identity pending verification.'),
    diagram: {x: 92, y: 400, w: 145, h: 55},
  },
  {
    id: 'coolant',
    name: 'Engine coolant',
    category: 'consumable',
    quantity: 1,
    requirement: 'required',
    description: 'Service consumable. Correct type, capacity, drain/refill and bleed procedure must come from authoritative service data.',
    source: prototypeSource('No fluid quantity or specification is asserted in this prototype.'),
    diagram: {x: 610, y: 400, w: 130, h: 55},
  },
];

export const demoRelations: PartRelation[] = [
  {from: 'radiator', to: 'upper-mount-left', type: 'mounted_by', note: 'Upper support relationship'},
  {from: 'radiator', to: 'upper-mount-right', type: 'mounted_by', note: 'Upper support relationship'},
  {from: 'radiator', to: 'lower-cushions', type: 'seated_on', note: 'Lower isolation/support relationship'},
  {from: 'upper-mount-left', to: 'mount-fasteners', type: 'fastened_by', note: 'Fastener relationship'},
  {from: 'upper-mount-right', to: 'mount-fasteners', type: 'fastened_by', note: 'Fastener relationship'},
  {from: 'radiator', to: 'radiator-fan', type: 'attached_to', note: 'Cooling-air assembly relationship'},
  {from: 'radiator', to: 'condenser', type: 'adjacent_to', note: 'Adjacent heat exchanger; inspect, do not auto-add'},
  {from: 'radiator', to: 'upper-hose', type: 'fluid_connected_to', note: 'Cooling-circuit connection'},
  {from: 'radiator', to: 'lower-hose', type: 'fluid_connected_to', note: 'Cooling-circuit connection'},
  {from: 'radiator', to: 'coolant', type: 'serviced_with', note: 'Cooling system service consumable'},
  {from: 'radiator', to: 'condenser', type: 'inspect_when_servicing', note: 'Inspect for collision/handling damage while area is open'},
];

export const initialPartStates: Record<string, PartState> = {
  radiator: 'need',
  'upper-mount-left': 'not-sure',
  'upper-mount-right': 'not-sure',
  'lower-cushions': 'need',
  'mount-fasteners': 'inspect',
  'radiator-fan': 'have',
  condenser: 'inspect',
  'upper-hose': 'have',
  'lower-hose': 'have',
  coolant: 'need',
};

export const commerceSources = [
  {id: 'honda', name: 'Honda / dealer source', note: 'Preferred for OEM identity and genuine-part availability.'},
  {id: 'ebay', name: 'eBay', note: 'Search by exact verified OEM number or approved interchange.'},
  {id: 'retailer-a', name: 'Reputable retailer A', note: 'Adapter placeholder; provider to be selected after terms/API review.'},
  {id: 'retailer-b', name: 'Reputable retailer B', note: 'Adapter placeholder; provider to be selected after terms/API review.'},
  {id: 'web', name: 'Indexed web search', note: 'Fallback discovery only; listing claims never override verified fitment.'},
];
