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
  transmission: string;
  market: string;
  vinRecommended: boolean;
}

export interface SourceClaim {
  label: string;
  status: 'prototype' | 'verified';
  note: string;
  url?: string;
}

export interface PurchaseLink {
  name: string;
  url: string;
  kind: 'dealer-catalog' | 'oem-retailer' | 'marketplace';
  note: string;
}

export interface PartNode {
  id: string;
  name: string;
  category: 'main' | 'mount' | 'fastener' | 'hose' | 'fan' | 'adjacent' | 'consumable' | 'sensor';
  quantity: number;
  requirement: RequirementLevel;
  description: string;
  oemNumber?: string;
  supersededNumbers?: string[];
  source: SourceClaim;
  purchaseLinks?: PurchaseLink[];
  diagram: {x: number; y: number; w: number; h: number};
}

export interface PartRelation {
  from: string;
  to: string;
  type: RelationshipType;
  note: string;
  source: SourceClaim;
}

export const demoVehicle: VehicleConfig = {
  id: 'honda-civic-2009-hybrid-us',
  make: 'Honda',
  model: 'Civic',
  year: 2009,
  trim: 'MX Hybrid',
  body: '4-door Sedan',
  engine: '1.3L L4 electric/gas',
  transmission: 'KA CVT',
  market: 'US',
  vinRecommended: true,
};

const radiatorCatalogUrl = 'https://www.hondapartsnow.com/parts-list/2009-honda-civic--4dr_mx_hybrid-ka_cvt/electrical_exhaust_heater_fuel/radiator_denso.html';
const hoseCatalogUrl = 'https://www.hondapartsnow.com/parts-list/2009-honda-civic--4dr_mx_hybrid-ka_cvt/electrical_exhaust_heater_fuel/radiator_hose_reserve_tank.html';
const condenserCatalogUrl = 'https://www.hondapartsnow.com/parts-list/2009-honda-civic--4dr_mx_hybrid-ka_cvt/body_air_conditioning/a_c_condenser.html';

const catalogSource = (label: string, url: string, note: string): SourceClaim => ({
  label,
  status: 'verified',
  note,
  url,
});

const prototypeSource = (note: string): SourceClaim => ({
  label: 'Prototype relationship',
  status: 'prototype',
  note,
});

const radiatorCatalog = catalogSource(
  'Exact-configuration OEM catalog',
  radiatorCatalogUrl,
  'Catalog page explicitly targets 2009 Honda Civic 4 Door MX (HYBRID), KA CVT. This verifies catalog identity, not service-manual torque or installation procedure.',
);

const hoseCatalog = catalogSource(
  'Exact-configuration OEM hose/mount catalog',
  hoseCatalogUrl,
  'Catalog page explicitly targets 2009 Honda Civic 4 Door MX (HYBRID), KA CVT and lists radiator hoses, mounting brackets, cushions and associated hardware.',
);

const condenserCatalog = catalogSource(
  'Exact-configuration OEM condenser catalog',
  condenserCatalogUrl,
  'Catalog page explicitly targets 2009 Honda Civic 4 Door MX (HYBRID), KA CVT and lists the condenser and its mounting hardware.',
);

export const sourceLedger = [
  {
    id: 'radiator-catalog',
    label: 'Radiator (Denso) — exact 2009 Civic Hybrid KA CVT catalog',
    url: radiatorCatalogUrl,
    scope: 'Radiator, fan/shroud, cap, drain hardware, water-temperature sensor and related fasteners',
  },
  {
    id: 'hose-mount-catalog',
    label: 'Radiator Hose / Reserve Tank — exact 2009 Civic Hybrid KA CVT catalog',
    url: hoseCatalogUrl,
    scope: 'Upper/lower hoses, hose clips, radiator mounting bracket, upper/lower cushions and related bolts',
  },
  {
    id: 'condenser-catalog',
    label: 'A/C Condenser — exact 2009 Civic Hybrid KA CVT catalog',
    url: condenserCatalogUrl,
    scope: 'Condenser, upper brackets, rubber mounts, collars, O-rings and associated fasteners',
  },
];

export const demoParts: PartNode[] = [
  {
    id: 'radiator',
    name: 'Radiator (Denso)',
    category: 'main',
    quantity: 1,
    requirement: 'required',
    description: 'Primary repair target. Catalog fitment is specific to the 2009 Civic 4-door MX Hybrid with KA CVT.',
    oemNumber: '19010-RRH-901',
    source: radiatorCatalog,
    purchaseLinks: [
      {
        name: 'HondaPartsNow',
        url: 'https://www.hondapartsnow.com/genuine/honda~radiator~19010-rrh-901.html',
        kind: 'dealer-catalog',
        note: 'Genuine Honda listing with 2009 MX Hybrid KA CVT fitment shown.',
      },
      {
        name: 'Honda Factory Parts',
        url: 'https://www.hondafactoryparts.com/v-2009-honda-civic--hybrid--1-3l-l4-electric-gas/cooling-system--cooling-system',
        kind: 'dealer-catalog',
        note: 'Vehicle-specific cooling-system catalog listing OEM 19010-RRH-901.',
      },
      {
        name: 'Honda Parts Online',
        url: 'https://www.hondapartsonline.net/oem-parts/honda-radiator-assembly-19010rrh901',
        kind: 'oem-retailer',
        note: 'Genuine Honda product page for OEM 19010-RRH-901.',
      },
      {
        name: 'AutoPartsPrime',
        url: 'https://www.autopartsprime.com/honda/radiator-denso/oe-19010rrh901',
        kind: 'oem-retailer',
        note: 'Genuine Honda product page with 2009 MX Hybrid KA CVT fitment.',
      },
      {
        name: 'eBay',
        url: 'https://www.ebay.com/itm/306214898307',
        kind: 'marketplace',
        note: 'Example current OEM-number listing. Marketplace seller/stock must be rechecked at purchase time.',
      },
    ],
    diagram: {x: 325, y: 180, w: 180, h: 190},
  },
  {
    id: 'upper-brackets',
    name: 'Upper radiator mounting brackets',
    category: 'mount',
    quantity: 2,
    requirement: 'required',
    description: 'Two upper radiator mounting brackets are listed for the exact vehicle configuration.',
    oemNumber: '74171-SNA-A00',
    source: hoseCatalog,
    diagram: {x: 340, y: 65, w: 150, h: 60},
  },
  {
    id: 'upper-cushions',
    name: 'Upper radiator mounting cushions',
    category: 'mount',
    quantity: 2,
    requirement: 'normally-reusable',
    description: 'Upper isolation cushions. Presence is required; replacement depends on condition.',
    oemNumber: '74173-SJ4-000',
    source: hoseCatalog,
    diagram: {x: 515, y: 70, w: 155, h: 55},
  },
  {
    id: 'lower-cushions',
    name: 'Lower radiator mounting cushions',
    category: 'mount',
    quantity: 2,
    requirement: 'normally-reusable',
    description: 'Lower isolation/support cushions. The catalog lists the older number as superseded by the current service number.',
    oemNumber: '74172-S5A-010',
    supersededNumbers: ['74172-S5A-000'],
    source: hoseCatalog,
    diagram: {x: 355, y: 425, w: 150, h: 55},
  },
  {
    id: 'mount-bolts',
    name: 'Upper mount bolt-washers (6×16)',
    category: 'fastener',
    quantity: 2,
    requirement: 'inspect',
    description: 'Catalog-associated 6×16 bolt-washers. Reuse policy and torque remain locked until service information is verified.',
    oemNumber: '93405-06016-04',
    source: hoseCatalog,
    diagram: {x: 690, y: 88, w: 110, h: 55},
  },
  {
    id: 'radiator-shroud',
    name: 'Radiator fan shroud',
    category: 'fan',
    quantity: 1,
    requirement: 'inspect',
    description: 'Denso radiator shroud listed in the exact radiator catalog.',
    oemNumber: '19015-RMX-A51',
    source: radiatorCatalog,
    diagram: {x: 575, y: 205, w: 150, h: 105},
  },
  {
    id: 'radiator-fan',
    name: 'Radiator cooling fan',
    category: 'fan',
    quantity: 1,
    requirement: 'inspect',
    description: 'Primary Denso cooling fan blade listed with the radiator assembly.',
    oemNumber: '19020-RSH-E01',
    source: radiatorCatalog,
    diagram: {x: 610, y: 330, w: 140, h: 55},
  },
  {
    id: 'radiator-fan-motor',
    name: 'Radiator cooling fan motor',
    category: 'fan',
    quantity: 1,
    requirement: 'inspect',
    description: 'Denso cooling fan motor listed in the exact radiator catalog.',
    oemNumber: '19030-RMX-A51',
    source: radiatorCatalog,
    diagram: {x: 610, y: 395, w: 140, h: 55},
  },
  {
    id: 'secondary-fan',
    name: 'Secondary cooling fan',
    category: 'fan',
    quantity: 1,
    requirement: 'inspect',
    description: 'Second Denso cooling fan listed in the exact radiator catalog.',
    oemNumber: '38611-RMX-A51',
    source: radiatorCatalog,
    diagram: {x: 655, y: 260, w: 130, h: 55},
  },
  {
    id: 'secondary-shroud',
    name: 'Secondary fan sub-shroud',
    category: 'fan',
    quantity: 1,
    requirement: 'inspect',
    description: 'Sub-shroud listed with the second cooling fan.',
    oemNumber: '38615-RRA-A01',
    source: radiatorCatalog,
    diagram: {x: 655, y: 195, w: 130, h: 55},
  },
  {
    id: 'secondary-fan-motor',
    name: 'Secondary cooling fan motor',
    category: 'fan',
    quantity: 1,
    requirement: 'inspect',
    description: 'Denso motor for the secondary cooling fan.',
    oemNumber: '38616-RFE-003',
    source: radiatorCatalog,
    diagram: {x: 655, y: 325, w: 130, h: 55},
  },
  {
    id: 'radiator-cap',
    name: 'Radiator cap',
    category: 'fastener',
    quantity: 1,
    requirement: 'normally-reusable',
    description: 'Denso radiator cap listed for the exact configuration.',
    oemNumber: '19045-RAA-003',
    source: radiatorCatalog,
    diagram: {x: 275, y: 145, w: 105, h: 45},
  },
  {
    id: 'upper-hose',
    name: 'Upper radiator hose',
    category: 'hose',
    quantity: 1,
    requirement: 'inspect',
    description: 'Water hose from radiator to thermostat housing for the Civic Hybrid.',
    oemNumber: '19501-RMX-000',
    source: hoseCatalog,
    diagram: {x: 55, y: 85, w: 160, h: 55},
  },
  {
    id: 'lower-hose',
    name: 'Lower radiator hose B',
    category: 'hose',
    quantity: 1,
    requirement: 'inspect',
    description: 'Lower radiator water hose B for the Civic Hybrid. The cooling circuit also contains additional lower hose/pipe sections, so this MVP does not claim this one hose represents the entire lower circuit.',
    oemNumber: '19504-RMX-000',
    source: hoseCatalog,
    diagram: {x: 55, y: 415, w: 160, h: 55},
  },
  {
    id: 'water-temp-sensor',
    name: 'Water temperature sensor',
    category: 'sensor',
    quantity: 1,
    requirement: 'inspect',
    description: 'Denso water-temperature sensor listed in the exact radiator catalog.',
    oemNumber: '37870-RTA-005',
    source: radiatorCatalog,
    diagram: {x: 220, y: 345, w: 125, h: 55},
  },
  {
    id: 'drain-bolt',
    name: 'Radiator drain bolt',
    category: 'fastener',
    quantity: 1,
    requirement: 'normally-reusable',
    description: 'Denso radiator drain bolt. Reuse/replacement decision must follow service condition and verified procedure.',
    oemNumber: '19011-PH1-621',
    source: radiatorCatalog,
    diagram: {x: 255, y: 420, w: 105, h: 45},
  },
  {
    id: 'drain-gasket',
    name: 'Radiator drain gasket',
    category: 'fastener',
    quantity: 1,
    requirement: 'inspect',
    description: 'Denso drain gasket associated with the radiator drain bolt. Single-use status is not asserted in this prototype.',
    oemNumber: '19012-671-300',
    source: radiatorCatalog,
    diagram: {x: 245, y: 475, w: 120, h: 45},
  },
  {
    id: 'radiator-seals',
    name: 'Radiator seals',
    category: 'fastener',
    quantity: 2,
    requirement: 'inspect',
    description: 'Two seals are listed in the exact Denso radiator catalog.',
    oemNumber: '19013-RNA-J01',
    source: radiatorCatalog,
    diagram: {x: 390, y: 485, w: 120, h: 45},
  },
  {
    id: 'condenser',
    name: 'A/C condenser',
    category: 'adjacent',
    quantity: 1,
    requirement: 'adjacent-only',
    description: 'Adjacent heat exchanger. It is part of a separate refrigerant circuit and should never be auto-added merely because the radiator is replaced.',
    oemNumber: '80110-SNA-A42',
    source: condenserCatalog,
    diagram: {x: 70, y: 205, w: 165, h: 120},
  },
  {
    id: 'condenser-bracket-right',
    name: 'Right upper condenser bracket',
    category: 'adjacent',
    quantity: 1,
    requirement: 'adjacent-only',
    description: 'Condenser-specific upper mounting bracket. Inspect only when condenser damage or missing hardware is suspected.',
    oemNumber: '80115-SNA-A00',
    source: condenserCatalog,
    diagram: {x: 35, y: 155, w: 135, h: 45},
  },
  {
    id: 'condenser-bracket-left',
    name: 'Left upper condenser bracket',
    category: 'adjacent',
    quantity: 1,
    requirement: 'adjacent-only',
    description: 'Condenser-specific upper mounting bracket. Inspect only when condenser damage or missing hardware is suspected.',
    oemNumber: '80116-SNA-A00',
    source: condenserCatalog,
    diagram: {x: 125, y: 340, w: 135, h: 45},
  },
  {
    id: 'coolant',
    name: 'Engine coolant',
    category: 'consumable',
    quantity: 1,
    requirement: 'required',
    description: 'A radiator replacement requires cooling-system service, but the exact coolant specification, quantity and bleed procedure are deliberately withheld until Honda service information is verified.',
    source: prototypeSource('Service-spec source not yet licensed/verified. No coolant quantity or bleed procedure is asserted.'),
    diagram: {x: 525, y: 470, w: 130, h: 55},
  },
];

const catalogRelation = (note: string, source: SourceClaim): SourceClaim => ({
  ...source,
  note: `${note} Relationship is derived from the exact-configuration OEM exploded catalog; service sequence still requires service-manual verification.`,
});

export const demoRelations: PartRelation[] = [
  {from: 'radiator', to: 'upper-brackets', type: 'mounted_by', note: 'Upper radiator support hardware', source: catalogRelation('Bracket and radiator are shown in the same exact vehicle cooling catalog.', hoseCatalog)},
  {from: 'upper-brackets', to: 'upper-cushions', type: 'seated_on', note: 'Upper isolation cushion at bracket/radiator interface', source: catalogRelation('Upper cushion is listed with the radiator mounting hardware.', hoseCatalog)},
  {from: 'radiator', to: 'lower-cushions', type: 'seated_on', note: 'Lower radiator support/isolation', source: catalogRelation('Lower cushions are listed in the same exact vehicle mounting catalog.', hoseCatalog)},
  {from: 'upper-brackets', to: 'mount-bolts', type: 'fastened_by', note: 'Associated upper mounting bolt-washers', source: catalogRelation('Two 6×16 bolt-washers are listed with the mounting hardware.', hoseCatalog)},
  {from: 'radiator', to: 'radiator-shroud', type: 'attached_to', note: 'Cooling-air shroud belongs to radiator assembly', source: catalogRelation('Radiator and shroud are listed in one Denso radiator assembly catalog.', radiatorCatalog)},
  {from: 'radiator-shroud', to: 'radiator-fan', type: 'attached_to', note: 'Fan belongs to shroud/cooling-air assembly', source: catalogRelation('Fan and shroud are listed together in the Denso radiator diagram.', radiatorCatalog)},
  {from: 'radiator-fan', to: 'radiator-fan-motor', type: 'attached_to', note: 'Fan/motor relationship', source: catalogRelation('Fan and motor are listed together in the Denso radiator diagram.', radiatorCatalog)},
  {from: 'radiator', to: 'secondary-shroud', type: 'attached_to', note: 'Secondary fan sub-shroud in radiator assembly', source: catalogRelation('Second fan/sub-shroud are listed in the Denso radiator diagram.', radiatorCatalog)},
  {from: 'secondary-shroud', to: 'secondary-fan', type: 'attached_to', note: 'Secondary fan/sub-shroud relationship', source: catalogRelation('Second fan/sub-shroud are listed together.', radiatorCatalog)},
  {from: 'secondary-fan', to: 'secondary-fan-motor', type: 'attached_to', note: 'Secondary fan/motor relationship', source: catalogRelation('Second fan and motor are listed together.', radiatorCatalog)},
  {from: 'radiator', to: 'radiator-cap', type: 'attached_to', note: 'Radiator cap in Denso cooling assembly', source: catalogRelation('Radiator cap is listed in the exact Denso radiator catalog.', radiatorCatalog)},
  {from: 'radiator', to: 'upper-hose', type: 'fluid_connected_to', note: 'Upper cooling-circuit connection', source: catalogRelation('Upper hose is listed as the Civic Hybrid radiator-to-thermostat-housing hose.', hoseCatalog)},
  {from: 'radiator', to: 'lower-hose', type: 'fluid_connected_to', note: 'Lower cooling-circuit connection', source: catalogRelation('Lower hose B is listed in the exact Civic Hybrid radiator-hose catalog.', hoseCatalog)},
  {from: 'radiator', to: 'water-temp-sensor', type: 'attached_to', note: 'Water-temperature sensor in radiator assembly', source: catalogRelation('Sensor is listed in the exact Denso radiator catalog.', radiatorCatalog)},
  {from: 'radiator', to: 'drain-bolt', type: 'attached_to', note: 'Radiator drain hardware', source: catalogRelation('Drain bolt is listed with the exact radiator.', radiatorCatalog)},
  {from: 'drain-bolt', to: 'drain-gasket', type: 'seated_on', note: 'Drain gasket associated with drain hardware', source: catalogRelation('Drain gasket is listed beside the drain bolt in the Denso radiator catalog.', radiatorCatalog)},
  {from: 'radiator', to: 'radiator-seals', type: 'attached_to', note: 'Two radiator seals', source: catalogRelation('Two radiator seals are listed in the exact Denso radiator catalog.', radiatorCatalog)},
  {from: 'radiator', to: 'condenser', type: 'adjacent_to', note: 'Adjacent front heat exchanger; separate refrigerant circuit', source: prototypeSource('Physical adjacency is the product hypothesis being demonstrated; do not interpret this as permission to open the A/C circuit.')},
  {from: 'condenser', to: 'condenser-bracket-right', type: 'mounted_by', note: 'Right upper condenser bracket', source: catalogRelation('Right bracket and condenser are listed in the exact condenser catalog.', condenserCatalog)},
  {from: 'condenser', to: 'condenser-bracket-left', type: 'mounted_by', note: 'Left upper condenser bracket', source: catalogRelation('Left bracket and condenser are listed in the exact condenser catalog.', condenserCatalog)},
  {from: 'radiator', to: 'coolant', type: 'serviced_with', note: 'Cooling-system service consumable', source: prototypeSource('The need to restore coolant after radiator service is mechanically obvious, but exact type/capacity/bleed steps remain intentionally locked until service data is verified.')},
  {from: 'radiator', to: 'condenser', type: 'inspect_when_servicing', note: 'Inspect adjacent condenser for collision/handling damage while exposed', source: prototypeSource('Inspection recommendation; not an OEM service claim.')},
];

export const initialPartStates: Record<string, PartState> = {
  radiator: 'need',
  'upper-brackets': 'not-sure',
  'upper-cushions': 'not-sure',
  'lower-cushions': 'need',
  'mount-bolts': 'inspect',
  'radiator-shroud': 'have',
  'radiator-fan': 'have',
  'radiator-fan-motor': 'have',
  'secondary-fan': 'have',
  'secondary-shroud': 'have',
  'secondary-fan-motor': 'have',
  'radiator-cap': 'have',
  'upper-hose': 'have',
  'lower-hose': 'have',
  'water-temp-sensor': 'inspect',
  'drain-bolt': 'have',
  'drain-gasket': 'inspect',
  'radiator-seals': 'inspect',
  condenser: 'inspect',
  'condenser-bracket-right': 'inspect',
  'condenser-bracket-left': 'inspect',
  coolant: 'need',
};

export const commerceSources = [
  {id: 'hondapartsnow', name: 'HondaPartsNow', note: 'Exact OEM-number catalog/product lookup.'},
  {id: 'hondafactoryparts', name: 'Honda Factory Parts', note: 'Dealer catalog lookup by exact OEM number.'},
  {id: 'hondapartsonline', name: 'Honda Parts Online', note: 'Genuine Honda retailer lookup by exact OEM number.'},
  {id: 'autopartsprime', name: 'AutoPartsPrime', note: 'OEM retailer lookup by exact part number.'},
  {id: 'ebay', name: 'eBay', note: 'Marketplace lookup; seller authenticity/stock must be rechecked.'},
];
