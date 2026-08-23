import {
  demoParts,
  demoRelations,
  initialPartStates,
  sourceLedger as coolingSourceLedger,
  type PartNode,
  type PartRelation,
  type PartState,
  type RequirementLevel,
  type SourceClaim,
} from './partGraphDemo';

export type RepairBlockId = 'cooling' | 'air-conditioning' | 'drivetrain' | 'safety';

export interface RepairSourceEntry {
  id: string;
  label: string;
  url: string;
  scope: string;
}

export interface RepairGraphDefinition {
  id: string;
  blockId: RepairBlockId;
  label: string;
  shortLabel: string;
  summary: string;
  defaultTargetPartId: string;
  parts: PartNode[];
  relations: PartRelation[];
  sources: RepairSourceEntry[];
  warning?: string;
  defaultStates?: Record<string, PartState>;
}

export interface RepairBlockDefinition {
  id: RepairBlockId;
  label: string;
  description: string;
  graphs: RepairGraphDefinition[];
}

const exactCatalogSource = (label: string, url: string, scope: string): SourceClaim => ({
  label,
  status: 'verified',
  url,
  note: `${scope} The source page is scoped to 2009 Honda Civic 4 Door MX (HYBRID), KA CVT. Catalog identity does not substitute for Honda service-manual procedures or torque specifications.`,
});

const layout = [
  {x: 330, y: 205, w: 165, h: 82},
  {x: 80, y: 95, w: 155, h: 64},
  {x: 585, y: 95, w: 155, h: 64},
  {x: 70, y: 245, w: 155, h: 64},
  {x: 595, y: 245, w: 155, h: 64},
  {x: 90, y: 395, w: 155, h: 64},
  {x: 575, y: 395, w: 155, h: 64},
  {x: 330, y: 70, w: 165, h: 64},
  {x: 330, y: 385, w: 165, h: 64},
  {x: 330, y: 475, w: 165, h: 55},
];

function part(
  id: string,
  name: string,
  oemNumber: string,
  requirement: RequirementLevel,
  source: SourceClaim,
  index: number,
  options?: {quantity?: number; description?: string; supersededNumbers?: string[]; category?: PartNode['category']},
): PartNode {
  return {
    id,
    name,
    oemNumber,
    requirement,
    quantity: options?.quantity ?? 1,
    description: options?.description ?? 'Exact-configuration catalog component. Condition and replacement need must be confirmed for the repair being performed.',
    supersededNumbers: options?.supersededNumbers,
    category: options?.category ?? (index === 0 ? 'main' : 'adjacent'),
    source,
    diagram: layout[index % layout.length],
  };
}

function rel(from: string, to: string, type: PartRelation['type'], source: SourceClaim, note: string): PartRelation {
  return {from, to, type, note, source};
}

function sourceEntry(id: string, label: string, url: string, scope: string): RepairSourceEntry {
  return {id, label, url, scope};
}

function defaultStates(parts: PartNode[], targetId: string): Record<string, PartState> {
  return Object.fromEntries(parts.map((item) => {
    if (item.id === targetId) return [item.id, 'need'];
    if (item.requirement === 'inspect' || item.requirement === 'normally-reusable' || item.requirement === 'adjacent-only') return [item.id, 'inspect'];
    return [item.id, 'not-sure'];
  }));
}

const acCondenserUrl = 'https://www.hondapartsnow.com/parts-list/2009-honda-civic--4dr_mx_hybrid-ka_cvt/body_air_conditioning/a_c_condenser.html';
const acHosesUrl = 'https://www.hondapartsnow.com/parts-list/2009-honda-civic--4dr_mx_hybrid-ka_cvt/body_air_conditioning/a_c_hoses_pipes.html';
const acCompressorUrl = 'https://www.hondapartsnow.com/parts-list/2009-honda-civic--4dr_mx_hybrid-ka_cvt/body_air_conditioning/a_c_compressor.html';
const driveshaftUrl = 'https://www.hondapartsnow.com/parts-list/2009-honda-civic--4dr_mx_hybrid-ka_cvt/chassis/driveshaft_half_shaft.html';
const engineMountUrl = 'https://www.hondapartsnow.com/parts-list/2009-honda-civic--4dr_mx_hybrid-ka_cvt/body_air_conditioning/engine_mounts.html';
const transmissionCaseUrl = 'https://www.hondapartsnow.com/parts-list/2009-honda-civic--4dr_mx_hybrid-ka_cvt/transmission_automatic/transmission_case.html';
const frontBrakeUrl = 'https://www.hondapartsnow.com/parts-list/2009-honda-civic--4dr_mx_hybrid-ka_cvt/chassis/front_brake.html';
const masterBrakeUrl = 'https://www.hondapartsnow.com/parts-list/2009-honda-civic--4dr_mx_hybrid-ka_cvt/chassis/brake_master_cylinder_master_power.html';
const vsaUrl = 'https://www.hondapartsnow.com/parts-list/2009-honda-civic--4dr_mx_hybrid-ka_cvt/chassis/vsa_modulator.html';
const driverSrsUrl = 'https://www.hondapartsnow.com/parts-list/2009-honda-civic--4dr_mx_hybrid-ka_cvt/chassis/steering_wheel_srs.html';

const acCondenserSource = exactCatalogSource('A/C condenser catalog', acCondenserUrl, 'Condenser, receiver, mounts, brackets, O-rings and fasteners.');
const acHosesSource = exactCatalogSource('A/C hoses / pipes catalog', acHosesUrl, 'Suction/discharge hoses, receiver/pipe assemblies, pressure sensor, service caps, clamps and O-rings.');
const acCompressorSource = exactCatalogSource('A/C compressor catalog', acCompressorUrl, 'Compressor, clutch/field coil, holders, safety valve and mounting hardware.');
const driveshaftSource = exactCatalogSource('Driveshaft / half-shaft catalog', driveshaftUrl, 'Left/right driveshafts, joint sets and inboard/outboard boot sets.');
const engineMountSource = exactCatalogSource('Engine mounts catalog', engineMountUrl, 'Engine/transmission mounts, stays, torque rod and associated mounting hardware.');
const transmissionCaseSource = exactCatalogSource('CVT transmission case catalog', transmissionCaseUrl, 'Transmission case, oil pan, gasket, breather and related case hardware.');
const frontBrakeSource = exactCatalogSource('Front brake catalog', frontBrakeUrl, 'Front calipers, pads, rotors, shims, bleeders and caliper mounting hardware.');
const masterBrakeSource = exactCatalogSource('Brake master cylinder / master power catalog', masterBrakeUrl, 'Master-cylinder, servo, reservoir, cap, hoses and gasket.');
const vsaSource = exactCatalogSource('VSA modulator catalog', vsaUrl, 'VSA modulator, bracket, rubber mounts and mounting bolts.');
const driverSrsSource = exactCatalogSource('Steering wheel (SRS) catalog', driverSrsUrl, 'Driver SRS module and its steering-wheel mounting hardware.');

const acCondenserParts = [
  part('ac-condenser', 'A/C condenser', '80110-SNA-A42', 'required', acCondenserSource, 0),
  part('ac-condenser-right-bracket', 'Right upper condenser bracket', '80115-SNA-A00', 'inspect', acCondenserSource, 1),
  part('ac-condenser-left-bracket', 'Left upper condenser bracket', '80116-SNA-A00', 'inspect', acCondenserSource, 2),
  part('ac-condenser-rubber-mounts', 'Condenser rubber mounts', '80106-SDR-A00', 'inspect', acCondenserSource, 3, {quantity: 2}),
  part('ac-condenser-lower-mounts', 'Condenser mounts', '80175-SE0-000', 'inspect', acCondenserSource, 4, {quantity: 2}),
  part('ac-condenser-collars', 'Condenser distance collars', '38609-SA5-000', 'inspect', acCondenserSource, 5, {quantity: 2}),
  part('ac-receiver', 'A/C receiver', '80351-SDC-A01', 'inspect', acCondenserSource, 6),
  part('ac-receiver-clamp', 'Receiver clamp', '80352-SNA-A01', 'inspect', acCondenserSource, 7),
  part('ac-condenser-o-rings', 'Condenser 8 mm O-rings', '80873-ST7-000', 'inspect', acCondenserSource, 8, {quantity: 2, category: 'fastener'}),
  part('ac-condenser-bolts', 'Condenser bolt-washers (6×30)', '93405-06030-08', 'inspect', acCondenserSource, 9, {quantity: 2, category: 'fastener'}),
];

const acCondenserRelations = [
  rel('ac-condenser', 'ac-condenser-right-bracket', 'mounted_by', acCondenserSource, 'Right upper condenser support.'),
  rel('ac-condenser', 'ac-condenser-left-bracket', 'mounted_by', acCondenserSource, 'Left upper condenser support.'),
  rel('ac-condenser', 'ac-condenser-rubber-mounts', 'seated_on', acCondenserSource, 'Rubber isolation at condenser mounting points.'),
  rel('ac-condenser', 'ac-condenser-lower-mounts', 'mounted_by', acCondenserSource, 'Catalog condenser mounts.'),
  rel('ac-condenser', 'ac-condenser-collars', 'mounted_by', acCondenserSource, 'Distance collars listed with condenser mounting hardware.'),
  rel('ac-condenser', 'ac-receiver', 'attached_to', acCondenserSource, 'Receiver is listed in the condenser assembly.'),
  rel('ac-receiver', 'ac-receiver-clamp', 'mounted_by', acCondenserSource, 'Receiver clamp.'),
  rel('ac-condenser', 'ac-condenser-o-rings', 'fluid_connected_to', acCondenserSource, 'Catalog O-rings used at refrigerant connections.'),
  rel('ac-condenser-right-bracket', 'ac-condenser-bolts', 'fastened_by', acCondenserSource, 'Associated condenser mounting bolts.'),
];

const acHoseParts = [
  part('ac-discharge-hose', 'A/C discharge hose', '80316-SNC-A02', 'required', acHosesSource, 0, {category: 'hose'}),
  part('ac-suction-hose', 'A/C suction hose', '80312-SNC-A01', 'inspect', acHosesSource, 1, {category: 'hose'}),
  part('ac-pipe-assembly', 'A/C pipe assembly', '80320-SNC-A01', 'inspect', acHosesSource, 2, {category: 'hose'}),
  part('ac-receiver-pipe', 'Receiver pipe', '80341-SNC-G01', 'inspect', acHosesSource, 3, {category: 'hose'}),
  part('ac-discharge-clamp', 'Discharge-hose clamp', '80361-SNA-A00', 'inspect', acHosesSource, 4, {category: 'fastener'}),
  part('ac-pressure-sensor', 'A/C pressure sensor', '80450-T2F-A01', 'inspect', acHosesSource, 5, {category: 'sensor'}),
  part('ac-high-cap', 'High-side service cap', '80865-SL0-003', 'normally-reusable', acHosesSource, 6, {category: 'fastener'}),
  part('ac-low-cap', 'Low-side service cap', '80866-SJK-003', 'normally-reusable', acHosesSource, 7, {category: 'fastener'}),
  part('ac-o-ring-58', 'A/C O-ring (5/8")', '80871-SN7-003', 'inspect', acHosesSource, 8, {quantity: 3, category: 'fastener'}),
  part('ac-o-ring-12', 'A/C O-ring (1/2")', '80872-SN7-003', 'inspect', acHosesSource, 9, {quantity: 2, category: 'fastener'}),
];

const acHoseRelations = [
  rel('ac-discharge-hose', 'ac-discharge-clamp', 'mounted_by', acHosesSource, 'Discharge-hose clamp listed with A/C piping.'),
  rel('ac-discharge-hose', 'ac-o-ring-58', 'fluid_connected_to', acHosesSource, 'Refrigerant sealing hardware in the same catalog.'),
  rel('ac-suction-hose', 'ac-o-ring-12', 'fluid_connected_to', acHosesSource, 'Refrigerant sealing hardware in the same catalog.'),
  rel('ac-pipe-assembly', 'ac-pressure-sensor', 'attached_to', acHosesSource, 'Pressure sensor belongs to the A/C pipe circuit.'),
  rel('ac-pipe-assembly', 'ac-high-cap', 'attached_to', acHosesSource, 'High-side service cap.'),
  rel('ac-suction-hose', 'ac-low-cap', 'attached_to', acHosesSource, 'Low-side service cap.'),
  rel('ac-pipe-assembly', 'ac-receiver-pipe', 'fluid_connected_to', acHosesSource, 'A/C refrigerant pipe network.'),
];

const acCompressorParts = [
  part('ac-compressor', 'A/C compressor', '38810-RMX-A02', 'required', acCompressorSource, 0),
  part('ac-compressor-clutch', 'Compressor clutch set', '38900-RMX-A01', 'inspect', acCompressorSource, 1),
  part('ac-compressor-coil', 'Compressor field coil set', '38924-RMX-A01', 'inspect', acCompressorSource, 2),
  part('ac-compressor-safety-valve', 'Compressor safety valve', '38801-PHM-004', 'inspect', acCompressorSource, 3, {category: 'sensor'}),
  part('ac-compressor-holder-a', 'Compressor cable holder A', '38873-RMX-A04', 'inspect', acCompressorSource, 4, {category: 'mount'}),
  part('ac-compressor-holder-b', 'Compressor cable holder B', '38874-RMX-A03', 'inspect', acCompressorSource, 5, {category: 'mount'}),
  part('ac-compressor-tube-holders', 'Compressor tube holders', '38875-RCJ-A01', 'inspect', acCompressorSource, 6, {quantity: 3, category: 'mount'}),
  part('ac-compressor-mount-bolts', 'Compressor flange bolts (10×80)', '95801-10080-08', 'inspect', acCompressorSource, 7, {quantity: 2, category: 'fastener'}),
];

const acCompressorRelations = [
  rel('ac-compressor', 'ac-compressor-clutch', 'attached_to', acCompressorSource, 'Compressor clutch set.'),
  rel('ac-compressor', 'ac-compressor-coil', 'attached_to', acCompressorSource, 'Compressor field coil.'),
  rel('ac-compressor', 'ac-compressor-safety-valve', 'attached_to', acCompressorSource, 'Safety valve sub-assembly.'),
  rel('ac-compressor', 'ac-compressor-holder-a', 'mounted_by', acCompressorSource, 'Compressor cable routing hardware.'),
  rel('ac-compressor', 'ac-compressor-holder-b', 'mounted_by', acCompressorSource, 'Compressor cable routing hardware.'),
  rel('ac-compressor', 'ac-compressor-tube-holders', 'mounted_by', acCompressorSource, 'Tube holders listed with compressor assembly.'),
  rel('ac-compressor', 'ac-compressor-mount-bolts', 'fastened_by', acCompressorSource, 'Compressor mounting bolts.'),
];

const driveshaftParts = [
  part('right-driveshaft', 'Right driveshaft assembly', '44305-SNC-010', 'required', driveshaftSource, 0),
  part('left-driveshaft', 'Left driveshaft assembly', '44306-SNC-010', 'adjacent-only', driveshaftSource, 1),
  part('outboard-joint-set', 'Outboard joint set', '44014-SNA-020', 'inspect', driveshaftSource, 2, {quantity: 2}),
  part('inboard-boot-set', 'Inboard boot set', '44017-S5A-010', 'inspect', driveshaftSource, 3, {quantity: 2}),
  part('outboard-boot-set', 'Outboard boot set', '44018-SAB-N22', 'inspect', driveshaftSource, 4, {quantity: 2}),
  part('inboard-joint-set', 'Inboard joint set', '44310-SYZ-305', 'inspect', driveshaftSource, 5),
];

const driveshaftRelations = [
  rel('right-driveshaft', 'outboard-joint-set', 'attached_to', driveshaftSource, 'Outboard joint component listed with half-shaft assembly.'),
  rel('right-driveshaft', 'inboard-boot-set', 'attached_to', driveshaftSource, 'Inboard boot set for half-shaft service.'),
  rel('right-driveshaft', 'outboard-boot-set', 'attached_to', driveshaftSource, 'Outboard boot set for half-shaft service.'),
  rel('right-driveshaft', 'inboard-joint-set', 'attached_to', driveshaftSource, 'Inboard joint component.'),
  rel('right-driveshaft', 'left-driveshaft', 'adjacent_to', driveshaftSource, 'Opposite-side shaft in the same drivetrain assembly; not automatically required.'),
];

const mountParts = [
  part('engine-side-mount', 'Engine-side rubber mount', '50820-SNC-043', 'required', engineMountSource, 0, {category: 'mount'}),
  part('transmission-mount', 'Transmission rubber mount', '50850-SNC-A91', 'inspect', engineMountSource, 1, {category: 'mount'}),
  part('engine-side-stay', 'Engine-side mounting stay', '50625-SNC-020', 'inspect', engineMountSource, 2, {category: 'mount'}),
  part('transmission-mount-base', 'Transmission mounting-base bracket', '50655-SNC-A01', 'inspect', engineMountSource, 3, {category: 'mount'}),
  part('lower-torque-bracket', 'Lower torque-rod bracket', '50690-SNC-A90', 'inspect', engineMountSource, 4, {category: 'mount'}),
  part('transmission-mount-stay', 'Transmission mounting stay', '50855-SNC-A00', 'inspect', engineMountSource, 5, {category: 'mount'}),
  part('lower-torque-rod', 'Lower torque rod', '50890-SNC-A91', 'inspect', engineMountSource, 6, {category: 'mount'}),
  part('mount-bolt-12x40', 'Mount flange bolts (12×40)', '90164-S5A-010', 'inspect', engineMountSource, 7, {quantity: 3, category: 'fastener'}),
  part('mount-bolt-12x31', 'Mount flange bolts (12×31)', '90165-SNC-A00', 'inspect', engineMountSource, 8, {quantity: 2, category: 'fastener'}),
];

const mountRelations = [
  rel('engine-side-mount', 'engine-side-stay', 'mounted_by', engineMountSource, 'Engine-side mount and stay.'),
  rel('transmission-mount', 'transmission-mount-base', 'mounted_by', engineMountSource, 'Transmission mount/base relationship.'),
  rel('transmission-mount', 'transmission-mount-stay', 'mounted_by', engineMountSource, 'Transmission mount stay.'),
  rel('lower-torque-rod', 'lower-torque-bracket', 'mounted_by', engineMountSource, 'Lower torque rod and bracket.'),
  rel('engine-side-mount', 'mount-bolt-12x40', 'fastened_by', engineMountSource, 'Catalog mounting fasteners.'),
  rel('transmission-mount', 'mount-bolt-12x31', 'fastened_by', engineMountSource, 'Catalog mounting fasteners.'),
];

const cvtCaseParts = [
  part('cvt-oil-pan', 'CVT oil pan', '21151-RPS-000', 'required', transmissionCaseSource, 0),
  part('cvt-case-rps', 'CVT transmission case (RPS)', '21210-RPS-306', 'conditional', transmissionCaseSource, 1, {description: 'One transmission-case service number listed in the exact vehicle catalog. The same reference position also lists another case; VIN/build verification is required before purchase.'}),
  part('cvt-case-rbl', 'CVT transmission case (RBL)', '21210-RBL-315', 'conditional', transmissionCaseSource, 2, {description: 'Alternative transmission-case service number listed at the same catalog reference. Do not choose between case variants without VIN/build verification.'}),
  part('cvt-pan-gasket', 'CVT oil-pan gasket', '21814-RPS-000', 'inspect', transmissionCaseSource, 3, {category: 'fastener'}),
  part('cvt-breather-cap', 'Transmission breather cap', '21396-P20-000', 'normally-reusable', transmissionCaseSource, 4),
  part('cvt-magnet', 'Transmission magnet', '25422-PN6-801', 'inspect', transmissionCaseSource, 5),
];

const cvtCaseRelations = [
  rel('cvt-oil-pan', 'cvt-pan-gasket', 'seated_on', transmissionCaseSource, 'Oil-pan gasket.'),
  rel('cvt-case-rps', 'cvt-oil-pan', 'attached_to', transmissionCaseSource, 'Oil pan belongs to transmission case assembly.'),
  rel('cvt-case-rbl', 'cvt-oil-pan', 'attached_to', transmissionCaseSource, 'Alternative case uses the catalog oil-pan assembly; exact case variant needs VIN/build confirmation.'),
  rel('cvt-case-rps', 'cvt-breather-cap', 'attached_to', transmissionCaseSource, 'Transmission breather cap.'),
  rel('cvt-oil-pan', 'cvt-magnet', 'attached_to', transmissionCaseSource, 'Transmission magnet listed with the case/pan assembly.'),
];

const frontBrakeParts = [
  part('front-brake-pads', 'Front brake pad set', '45022-S5B-J02', 'required', frontBrakeSource, 0, {supersededNumbers: ['45022-S5B-J01', '45022-S5B-J00']}),
  part('front-brake-rotors', 'Front brake discs / rotors', '45251-SNA-010', 'inspect', frontBrakeSource, 1, {quantity: 2}),
  part('front-caliper-right', 'Right front caliper', '45018-SNC-000', 'inspect', frontBrakeSource, 2),
  part('front-caliper-left', 'Left front caliper', '45019-SNC-000', 'inspect', frontBrakeSource, 3),
  part('front-caliper-set', 'Front caliper seal/service set', '01463-S2A-010', 'inspect', frontBrakeSource, 4, {quantity: 2}),
  part('front-pad-shims', 'Front brake shim set', '06455-S5A-J00', 'inspect', frontBrakeSource, 5),
  part('front-bleeder-screws', 'Front bleeder screws', '43352-SM4-951', 'normally-reusable', frontBrakeSource, 6, {quantity: 2, category: 'fastener'}),
  part('front-caliper-bolts', 'Caliper mounting bolts (12×21)', '90107-SM4-000', 'inspect', frontBrakeSource, 7, {quantity: 4, category: 'fastener'}),
];

const frontBrakeRelations = [
  rel('front-brake-pads', 'front-pad-shims', 'attached_to', frontBrakeSource, 'Pad/shim set relationship.'),
  rel('front-brake-pads', 'front-brake-rotors', 'adjacent_to', frontBrakeSource, 'Friction pair; rotor condition is a separate inspection decision.'),
  rel('front-caliper-right', 'front-brake-pads', 'attached_to', frontBrakeSource, 'Right caliper contains/acts on pad set.'),
  rel('front-caliper-left', 'front-brake-pads', 'attached_to', frontBrakeSource, 'Left caliper contains/acts on pad set.'),
  rel('front-caliper-right', 'front-bleeder-screws', 'attached_to', frontBrakeSource, 'Bleeder hardware is part of front caliper assembly.'),
  rel('front-caliper-left', 'front-bleeder-screws', 'attached_to', frontBrakeSource, 'Bleeder hardware is part of front caliper assembly.'),
  rel('front-caliper-right', 'front-caliper-bolts', 'fastened_by', frontBrakeSource, 'Caliper mounting bolts.'),
];

const vsaParts = [
  part('vsa-modulator', 'VSA modulator assembly', '57110-SNC-315', 'required', vsaSource, 0),
  part('vsa-rubber-mounts', 'VSA rubber mounts', '57101-SLJ-003', 'inspect', vsaSource, 1, {quantity: 3, category: 'mount'}),
  part('vsa-bracket', 'VSA modulator bracket', '57115-SNB-G00', 'inspect', vsaSource, 2, {category: 'mount'}),
  part('vsa-mounting-bolts', 'VSA mounting bolts', '57376-SNA-A00', 'inspect', vsaSource, 3, {quantity: 3, category: 'fastener'}),
  part('vsa-flange-bolts', 'VSA flange bolts (6×14)', '90003-SNA-010', 'inspect', vsaSource, 4, {quantity: 3, category: 'fastener'}),
];

const vsaRelations = [
  rel('vsa-modulator', 'vsa-rubber-mounts', 'seated_on', vsaSource, 'Three rubber mounts listed for VSA modulator.'),
  rel('vsa-modulator', 'vsa-bracket', 'mounted_by', vsaSource, 'VSA modulator bracket.'),
  rel('vsa-modulator', 'vsa-mounting-bolts', 'fastened_by', vsaSource, 'VSA mounting bolts.'),
  rel('vsa-bracket', 'vsa-flange-bolts', 'fastened_by', vsaSource, 'Bracket flange bolts.'),
];

const masterBrakeParts = [
  part('brake-master-cylinder', 'Brake master cylinder set', '01461-SNC-G01', 'required', masterBrakeSource, 0, {supersededNumbers: ['01461-SNC-G00']}),
  part('brake-servo', 'Brake servo assembly', '01469-SNC-G07', 'inspect', masterBrakeSource, 1, {supersededNumbers: ['01469-SNC-326']}),
  part('brake-reservoir', 'Brake-fluid reservoir', '46660-SNC-A02', 'inspect', masterBrakeSource, 2),
  part('brake-reservoir-set', 'Brake reservoir set', '46661-SNC-A01', 'conditional', masterBrakeSource, 3),
  part('brake-reservoir-cap', 'Brake reservoir cap', '46662-SNC-A01', 'normally-reusable', masterBrakeSource, 4),
  part('brake-reservoir-hose', 'Brake reservoir hose set', '46017-SNC-A00', 'inspect', masterBrakeSource, 5, {category: 'hose'}),
  part('brake-servo-gasket', 'Brake master-power gasket', '46191-S2K-000', 'inspect', masterBrakeSource, 6, {category: 'fastener'}),
];

const masterBrakeRelations = [
  rel('brake-master-cylinder', 'brake-reservoir', 'fluid_connected_to', masterBrakeSource, 'Master cylinder and reservoir system.'),
  rel('brake-reservoir', 'brake-reservoir-cap', 'attached_to', masterBrakeSource, 'Reservoir cap.'),
  rel('brake-reservoir', 'brake-reservoir-hose', 'fluid_connected_to', masterBrakeSource, 'Reservoir hose set.'),
  rel('brake-master-cylinder', 'brake-servo', 'mounted_by', masterBrakeSource, 'Master cylinder / servo assembly relationship.'),
  rel('brake-servo', 'brake-servo-gasket', 'seated_on', masterBrakeSource, 'Master-power gasket.'),
  rel('brake-reservoir', 'brake-reservoir-set', 'adjacent_to', masterBrakeSource, 'Catalog lists reservoir and reservoir-set service options; verify exact need before purchase.'),
];

const srsParts = [
  part('driver-srs-module', 'Driver airbag / SRS module', '77810-SNA-A82ZA', 'required', driverSrsSource, 0),
  part('srs-module-bolts', 'SRS module hex bolts (6×23)', '90134-S6A-A80', 'inspect', driverSrsSource, 1, {quantity: 2, category: 'fastener'}),
  part('steering-handle-bolt', 'Steering handle bolt', '90161-SV4-003', 'inspect', driverSrsSource, 2, {category: 'fastener'}),
  part('steering-body-cover', 'Steering-wheel body cover', '78518-SVA-A61ZA', 'inspect', driverSrsSource, 3),
];

const srsRelations = [
  rel('driver-srs-module', 'srs-module-bolts', 'fastened_by', driverSrsSource, 'Driver SRS module mounting bolts.'),
  rel('driver-srs-module', 'steering-body-cover', 'attached_to', driverSrsSource, 'Steering-wheel/SRS assembly component.'),
  rel('driver-srs-module', 'steering-handle-bolt', 'adjacent_to', driverSrsSource, 'Steering-wheel fastening hardware listed in the same SRS diagram.'),
];

const coolingGraph: RepairGraphDefinition = {
  id: 'front-cooling',
  blockId: 'cooling',
  label: 'Front cooling / radiator area',
  shortLabel: 'Front cooling',
  summary: 'Radiator, fans, mounts, hoses, sensor, drain hardware and adjacent condenser.',
  defaultTargetPartId: 'radiator',
  parts: demoParts,
  relations: demoRelations,
  sources: coolingSourceLedger,
  defaultStates: initialPartStates,
};

const graphs: RepairGraphDefinition[] = [
  coolingGraph,
  {
    id: 'ac-condenser', blockId: 'air-conditioning', label: 'A/C condenser & receiver', shortLabel: 'Condenser', summary: 'Condenser, receiver, brackets, mounts, seals and fasteners.', defaultTargetPartId: 'ac-condenser', parts: acCondenserParts, relations: acCondenserRelations,
    sources: [sourceEntry('ac-condenser', 'A/C Condenser — exact 2009 Civic Hybrid KA CVT catalog', acCondenserUrl, 'Condenser, receiver, mounts, brackets, O-rings and fasteners')],
    warning: 'A/C refrigerant is a pressurized regulated system. PartGraph can identify parts, but refrigerant recovery/evacuation/recharge procedure is intentionally not provided from catalog data.',
  },
  {
    id: 'ac-hoses', blockId: 'air-conditioning', label: 'A/C hoses & pipes', shortLabel: 'Hoses / pipes', summary: 'Suction/discharge lines, receiver pipe, pressure sensor, service caps and seals.', defaultTargetPartId: 'ac-discharge-hose', parts: acHoseParts, relations: acHoseRelations,
    sources: [sourceEntry('ac-hoses', 'A/C Hoses / Pipes — exact 2009 Civic Hybrid KA CVT catalog', acHosesUrl, 'Hoses, pipes, clamps, sensor, service caps and O-rings')],
    warning: 'Opening any refrigerant line requires proper recovery equipment and exact service procedure. Catalog identity does not authorize venting refrigerant.',
  },
  {
    id: 'ac-compressor', blockId: 'air-conditioning', label: 'A/C compressor', shortLabel: 'Compressor', summary: 'Compressor, clutch, field coil, safety valve, cable/tube holders and mounting hardware.', defaultTargetPartId: 'ac-compressor', parts: acCompressorParts, relations: acCompressorRelations,
    sources: [sourceEntry('ac-compressor', 'A/C Compressor — exact 2009 Civic Hybrid KA CVT catalog', acCompressorUrl, 'Compressor, clutch/coil, holders, valve and mounting hardware')],
    warning: 'Compressor service crosses refrigerant and electrical/mechanical safety boundaries. Exact oil quantity, evacuation and recharge procedure remain locked until service information is verified.',
  },
  {
    id: 'driveshafts', blockId: 'drivetrain', label: 'Driveshafts / half-shafts', shortLabel: 'Driveshafts', summary: 'Left/right driveshafts, CV joint and boot service components.', defaultTargetPartId: 'right-driveshaft', parts: driveshaftParts, relations: driveshaftRelations,
    sources: [sourceEntry('driveshafts', 'Driveshaft / Half Shaft — exact 2009 Civic Hybrid KA CVT catalog', driveshaftUrl, 'Left/right driveshafts, joints and boot sets')],
    warning: 'This graph identifies drivetrain parts only. Axle-nut torque, suspension separation and fluid-loss procedures require exact Honda service information.',
  },
  {
    id: 'powertrain-mounts', blockId: 'drivetrain', label: 'Engine & transmission mounts', shortLabel: 'Powertrain mounts', summary: 'Engine-side mount, transmission mount, stays, lower torque rod and mounting hardware.', defaultTargetPartId: 'engine-side-mount', parts: mountParts, relations: mountRelations,
    sources: [sourceEntry('engine-mounts', 'Engine Mounts — exact 2009 Civic Hybrid KA CVT catalog', engineMountUrl, 'Engine/transmission mounts, stays, torque rod and bolts')],
    warning: 'Supporting the engine/transmission safely is mandatory before mount removal. Torque values are not inferred from the parts catalog.',
  },
  {
    id: 'cvt-case', blockId: 'drivetrain', label: 'CVT case / oil pan', shortLabel: 'CVT case', summary: 'CVT case alternatives, oil pan, pan gasket, breather and magnet.', defaultTargetPartId: 'cvt-oil-pan', parts: cvtCaseParts, relations: cvtCaseRelations,
    sources: [sourceEntry('cvt-case', 'Transmission Case — exact 2009 Civic Hybrid KA CVT catalog', transmissionCaseUrl, 'Transmission case, oil pan, gasket, breather and magnet')],
    warning: 'The catalog lists more than one transmission-case service number at the same reference. PartGraph will not choose a case variant without a VIN/build-specific source.',
  },
  {
    id: 'front-brakes', blockId: 'safety', label: 'Front brakes', shortLabel: 'Front brakes', summary: 'Pads, rotors, left/right calipers, shims, bleeders and mounting hardware.', defaultTargetPartId: 'front-brake-pads', parts: frontBrakeParts, relations: frontBrakeRelations,
    sources: [sourceEntry('front-brakes', 'Front Brake — exact 2009 Civic Hybrid KA CVT catalog', frontBrakeUrl, 'Front pads, rotors, calipers, shims, bleeders and hardware')],
    warning: 'Brake work is safety-critical. This catalog graph helps identify parts only; torque, bleeding and roadworthiness checks require authoritative service information and competent inspection.',
  },
  {
    id: 'brake-master', blockId: 'safety', label: 'Brake master cylinder / servo', shortLabel: 'Master cylinder', summary: 'Master cylinder, servo, reservoir, hose, cap and gasket.', defaultTargetPartId: 'brake-master-cylinder', parts: masterBrakeParts, relations: masterBrakeRelations,
    sources: [sourceEntry('brake-master', 'Brake Master Cylinder / Master Power — exact 2009 Civic Hybrid KA CVT catalog', masterBrakeUrl, 'Master cylinder, servo, reservoir, hoses and gasket')],
    warning: 'Hydraulic brake service is safety-critical. The app does not infer bleeding sequence, fluid specification or final safety checks from catalog data.',
  },
  {
    id: 'vsa-modulator', blockId: 'safety', label: 'VSA / ABS modulator', shortLabel: 'VSA modulator', summary: 'VSA modulator, bracket, rubber mounts and fasteners.', defaultTargetPartId: 'vsa-modulator', parts: vsaParts, relations: vsaRelations,
    sources: [sourceEntry('vsa', 'VSA Modulator — exact 2009 Civic Hybrid KA CVT catalog', vsaUrl, 'VSA modulator, bracket, mounts and fasteners')],
    warning: 'VSA/ABS hydraulic and electronic service may require bleeding, diagnostics and calibration. PartGraph currently provides identification and relationship data only.',
  },
  {
    id: 'driver-srs', blockId: 'safety', label: 'Driver SRS / steering wheel', shortLabel: 'Driver SRS', summary: 'Driver SRS module and associated steering-wheel mounting hardware.', defaultTargetPartId: 'driver-srs-module', parts: srsParts, relations: srsRelations,
    sources: [sourceEntry('driver-srs', 'Steering Wheel (SRS) — exact 2009 Civic Hybrid KA CVT catalog', driverSrsUrl, 'Driver SRS module and steering-wheel hardware')],
    warning: 'SRS/airbag work can cause serious injury if handled incorrectly. PartGraph does not provide activation/disarming/removal procedure from a parts catalog.',
  },
];

export const repairBlocks: RepairBlockDefinition[] = [
  {id: 'cooling', label: 'Cooling', description: 'Cooling circuit and front heat-exchanger assembly.', graphs: graphs.filter((graph) => graph.blockId === 'cooling')},
  {id: 'air-conditioning', label: 'Air conditioning', description: 'Refrigerant circuit hardware: condenser, hoses/pipes and compressor.', graphs: graphs.filter((graph) => graph.blockId === 'air-conditioning')},
  {id: 'drivetrain', label: 'Drivetrain', description: 'Power delivery and support: driveshafts, powertrain mounts and CVT case.', graphs: graphs.filter((graph) => graph.blockId === 'drivetrain')},
  {id: 'safety', label: 'Safety', description: 'Brakes, VSA/ABS and driver SRS identification.', graphs: graphs.filter((graph) => graph.blockId === 'safety')},
];

export const publishedRepairGraphs = graphs;

export function getRepairBlock(id: RepairBlockId): RepairBlockDefinition {
  return repairBlocks.find((block) => block.id === id) ?? repairBlocks[0];
}

export function getRepairGraph(id: string): RepairGraphDefinition {
  return graphs.find((graph) => graph.id === id) ?? coolingGraph;
}

export function initialStatesForGraph(graph: RepairGraphDefinition): Record<string, PartState> {
  return graph.defaultStates ? {...graph.defaultStates} : defaultStates(graph.parts, graph.defaultTargetPartId);
}
