export type SixthGenPartState = 'need' | 'have' | 'inspect' | 'not-sure';
export type SixthGenRequirement = 'required' | 'inspect' | 'normally-reusable' | 'conditional';
export type SixthGenPartGroup = 'radiator' | 'fan' | 'hose' | 'mount' | 'hardware' | 'reservoir' | 'adjacent';

export interface SixthGenConfigurationInput {
  year: number;
  bodyTrim: string;
  emissionTransmission: string;
  sourceUrl: string;
}

export interface SixthGenPart {
  id: string;
  name: string;
  oemNumber: string;
  alternateNumbers?: string[];
  replacedNumbers?: string[];
  quantity: number;
  requirement: SixthGenRequirement;
  group: SixthGenPartGroup;
  note: string;
  sourceUrl: string;
}

export interface SixthGenCoolingResolution {
  status: 'verified' | 'data-unavailable';
  generation: 6;
  generationLabel: string;
  years: readonly number[];
  configurationLabel: string;
  sourceUrl: string;
  radiatorSourceUrl?: string;
  hoseSourceUrl?: string;
  radiatorNumber?: string;
  alternateRadiatorNumbers?: string[];
  parts: SixthGenPart[];
  note: string;
  researchQuery: string;
}

export const CIVIC_SIXTH_GEN_YEARS = [1996, 1997, 1998, 1999, 2000] as const;
export const CIVIC_SIXTH_GEN_LABEL = '6th Generation Civic · 1996–2000';

function normalized(value: string) {
  return value.toUpperCase().replace(/[^A-Z0-9]+/g, ' ').trim();
}

function exactCatalogPage(sourceUrl: string, page: 'radiator_denso' | 'radiator_hose') {
  const match = sourceUrl.match(/\/([^/]+)-parts\.html(?:\?.*)?$/i);
  if (!match) return sourceUrl;
  return `https://www.hondapartsnow.com/parts-list/${match[1]}/electrical_exhaust_heater_fuel/${page}.html`;
}

function radiatorFor(input: SixthGenConfigurationInput): {number?: string; alternates?: string[]; note: string} {
  const body = normalized(input.bodyTrim);
  const transmission = normalized(input.emissionTransmission);
  const isEx = /(^| )EX( |$)/.test(body);
  const isHx = /(^| )HX( |$)/.test(body);
  const isGx = /(^| )GX( |$)/.test(body);
  const isSi = /(^| )SI( |$)/.test(body);
  const is4At = transmission.includes('4AT');
  const is5Mt = transmission.includes('5MT');
  const isCvt = transmission.includes('CVT');

  if (input.year >= 1996 && input.year <= 1998) {
    if (isEx && is5Mt) return {number: '19010-P2R-A01', note: 'Denso radiator used by 1996–1998 EX manual-transmission configurations.'};
    if ((isEx || isHx || isGx) && (is4At || isCvt)) return {number: '19010-P2R-A51', note: 'Denso radiator used by EX automatic, HX CVT and the cataloged 1998 GX automatic configurations.'};
    if (is4At) return {number: '19010-P2F-A51', note: 'Denso radiator used by the cataloged DX/CX/LX automatic configurations.'};
    if (is5Mt) return {number: '19010-P2F-A01', note: 'Denso radiator used by the cataloged DX/CX/LX/HX manual configurations.'};
  }

  if (input.year === 1999 || input.year === 2000) {
    if (isSi && is5Mt) return {number: '19010-P2T-A01', note: 'Denso radiator cataloged for the Civic Si manual configuration.'};
    if (isGx || (isEx && is4At) || (isHx && isCvt)) {
      return {number: '19010-P7G-902', note: 'Complete radiator cataloged for EX automatic, HX CVT and GX automatic configurations.'};
    }
    if (is4At || is5Mt) {
      const is1999FourDoorExKaManual = input.year === 1999 && body.includes('4 DOOR EX') && transmission.includes('KA 5MT');
      return {
        number: '19010-P03-505',
        alternates: is1999FourDoorExKaManual ? ['19010-P2K-014'] : undefined,
        note: is1999FourDoorExKaManual
          ? 'The exact 1999 4 Door EX KA 5MT catalog lists both 19010-P03-505 and a Toyo supplier alternative, 19010-P2K-014. PartGraph does not silently choose between supplier variants.'
          : 'Current radiator service number shown for the cataloged base/manual and many automatic 1999–2000 configurations.',
      };
    }
  }

  return {note: 'No radiator identity rule has been verified for this exact catalog configuration yet.'};
}

function coolingFanMotor(year: number) {
  return year <= 1998 ? '19030-P1R-003' : '19030-PEJ-003';
}

function waterHoseClamp(emissionTransmission: string) {
  const transmission = normalized(emissionTransmission);
  if (transmission.includes('CVT')) return '19519-P2J-J61';
  if (transmission.includes('5MT')) return '19519-P08-013';
  if (transmission.includes('4AT')) return '19519-P2A-901';
  return '';
}

function part(
  input: Omit<SixthGenPart, 'quantity' | 'alternateNumbers' | 'replacedNumbers'> & {
    quantity?: number;
    alternateNumbers?: string[];
    replacedNumbers?: string[];
  },
): SixthGenPart {
  return {
    ...input,
    quantity: input.quantity ?? 1,
  };
}

export function resolveCivicSixthGenCooling(input: SixthGenConfigurationInput): SixthGenCoolingResolution {
  const configurationLabel = `${input.year} Honda Civic · ${input.bodyTrim} · ${input.emissionTransmission}`;
  const researchQuery = `${configurationLabel} OEM radiator cooling fan radiator hose mounting bracket part numbers`;

  if (!CIVIC_SIXTH_GEN_YEARS.includes(input.year as (typeof CIVIC_SIXTH_GEN_YEARS)[number])) {
    return {
      status: 'data-unavailable',
      generation: 6,
      generationLabel: CIVIC_SIXTH_GEN_LABEL,
      years: CIVIC_SIXTH_GEN_YEARS,
      configurationLabel,
      sourceUrl: input.sourceUrl,
      parts: [],
      note: 'This release publishes 6th-generation Civic cooling data only.',
      researchQuery,
    };
  }

  const radiator = radiatorFor(input);
  if (!radiator.number) {
    return {
      status: 'data-unavailable',
      generation: 6,
      generationLabel: CIVIC_SIXTH_GEN_LABEL,
      years: CIVIC_SIXTH_GEN_YEARS,
      configurationLabel,
      sourceUrl: input.sourceUrl,
      parts: [],
      note: radiator.note,
      researchQuery,
    };
  }

  const radiatorSourceUrl = exactCatalogPage(input.sourceUrl, 'radiator_denso');
  const hoseSourceUrl = exactCatalogPage(input.sourceUrl, 'radiator_hose');
  const clampNumber = waterHoseClamp(input.emissionTransmission);

  const parts: SixthGenPart[] = [
    part({
      id: 'radiator', name: 'Radiator', oemNumber: radiator.number, alternateNumbers: radiator.alternates,
      requirement: 'required', group: 'radiator', note: radiator.note, sourceUrl: radiatorSourceUrl,
    }),
    part({
      id: 'drain-bolt', name: 'Radiator drain bolt / petcock (Denso)', oemNumber: '19011-PH1-621',
      requirement: 'inspect', group: 'hardware', note: 'Denso radiator drain hardware. Supplier-specific radiators can use different drain hardware.', sourceUrl: radiatorSourceUrl,
    }),
    part({
      id: 'drain-gasket', name: 'Radiator drain gasket (Denso)', oemNumber: '19012-671-300',
      requirement: 'inspect', group: 'hardware', note: 'Denso drain gasket shown with the radiator assembly.', sourceUrl: radiatorSourceUrl,
    }),
    part({
      id: 'harness-clip', name: 'Radiator harness clip', oemNumber: '19017-PK1-003', replacedNumbers: ['19014-PK1-003'],
      requirement: 'normally-reusable', group: 'hardware', note: 'Current replacement shown for the older 19014-PK1-003 harness clip.', sourceUrl: radiatorSourceUrl,
    }),
    part({
      id: 'fan-shroud', name: 'Radiator fan shroud', oemNumber: '19015-P08-013',
      requirement: 'inspect', group: 'fan', note: 'Denso radiator fan shroud used across the researched 6th-generation cooling configurations.', sourceUrl: radiatorSourceUrl,
    }),
    part({
      id: 'cooling-fan', name: 'Radiator cooling fan', oemNumber: '19020-P08-003',
      requirement: 'inspect', group: 'fan', note: 'Cooling fan blade shown in the Denso radiator assembly.', sourceUrl: radiatorSourceUrl,
    }),
    part({
      id: 'fan-motor', name: 'Radiator cooling fan motor', oemNumber: coolingFanMotor(input.year),
      requirement: 'inspect', group: 'fan', note: input.year <= 1998 ? '1996–1998 Denso cooling-fan motor service number.' : '1999–2000 Denso cooling-fan motor service number.', sourceUrl: radiatorSourceUrl,
    }),
    part({
      id: 'connector-stay', name: 'Cooling-fan connector stay', oemNumber: '19033-P08-003',
      requirement: 'normally-reusable', group: 'mount', note: 'Connector stay shown with the radiator/fan assembly.', sourceUrl: radiatorSourceUrl,
    }),
    part({
      id: 'radiator-cap', name: 'Radiator cap', oemNumber: '19045-PAA-A01',
      requirement: 'inspect', group: 'radiator', note: 'Radiator cap shown in the Denso radiator assembly.', sourceUrl: radiatorSourceUrl,
    }),
    part({
      id: 'shroud-screws', name: 'Fan-shroud screw-washers (4×11)', oemNumber: '90041-P5A-003', quantity: 4,
      requirement: 'inspect', group: 'hardware', note: 'Catalog quantity: four.', sourceUrl: radiatorSourceUrl,
    }),
    part({
      id: 'fan-bolts', name: 'Fan/shroud bolt-washers (6×16)', oemNumber: '90042-PAA-A01', quantity: 4,
      requirement: 'inspect', group: 'hardware', note: 'Catalog quantity: four.', sourceUrl: radiatorSourceUrl,
    }),
    part({
      id: 'fan-nut', name: 'Cooling-fan hex nut (5 mm)', oemNumber: '90043-PD2-003',
      requirement: 'normally-reusable', group: 'hardware', note: 'Denso fan hardware.', sourceUrl: radiatorSourceUrl,
    }),
    part({
      id: 'upper-hose', name: 'Upper radiator water hose', oemNumber: '19501-P08-000',
      requirement: 'inspect', group: 'hose', note: 'Upper engine-to-radiator coolant hose.', sourceUrl: hoseSourceUrl,
    }),
    part({
      id: 'lower-hose', name: 'Lower radiator water hose', oemNumber: '19502-P2A-000',
      requirement: 'inspect', group: 'hose', note: 'Lower engine-to-radiator coolant hose.', sourceUrl: hoseSourceUrl,
    }),
    part({
      id: 'hose-clips', name: 'Water-hose clips', oemNumber: '19511-PA6-003', alternateNumbers: ['19511-P09-A01'], quantity: 2,
      requirement: 'inspect', group: 'hardware', note: 'The catalog shows origin/supplier-specific CHUO SPRING and TOGO clip alternatives. Do not order both sets without checking the installed style.', sourceUrl: hoseSourceUrl,
    }),
    ...(clampNumber ? [part({
      id: 'water-hose-clamp', name: 'Water-hose clamp', oemNumber: clampNumber,
      requirement: 'inspect' as const, group: 'hardware' as const, note: `Clamp number selected from the exact transmission family (${input.emissionTransmission}).`, sourceUrl: hoseSourceUrl,
    })] : []),
    part({
      id: 'upper-mount-bracket', name: 'Right upper radiator mounting bracket', oemNumber: '74171-SP0-010', replacedNumbers: ['74171-SP0-000'],
      requirement: 'inspect', group: 'mount', note: 'Right upper radiator mounting bracket. Older 74171-SP0-000 is replaced by 74171-SP0-010.', sourceUrl: hoseSourceUrl,
    }),
    part({
      id: 'lower-mount-cushions', name: 'Lower radiator mounting cushions', oemNumber: '74172-SR3-000', quantity: 2,
      requirement: 'inspect', group: 'mount', note: 'Catalog quantity: two lower isolation/support cushions.', sourceUrl: hoseSourceUrl,
    }),
    part({
      id: 'upper-mount-cushion', name: 'Upper radiator mounting cushion', oemNumber: '74173-SJ4-000',
      requirement: 'inspect', group: 'mount', note: 'Upper radiator isolation cushion.', sourceUrl: hoseSourceUrl,
    }),
    part({
      id: 'mount-bolts-a', name: 'Radiator mounting bolt-washers (6×16)', oemNumber: '93401-06016-04', quantity: 2,
      requirement: 'inspect', group: 'hardware', note: 'Catalog quantity: two for this mounting fastener line.', sourceUrl: hoseSourceUrl,
    }),
    part({
      id: 'mount-bolt-b', name: 'Radiator mounting bolt-washer (6×16)', oemNumber: '93405-06016-04',
      requirement: 'inspect', group: 'hardware', note: 'Second 6×16 bolt-washer family shown in the radiator-hose/mount catalog.', sourceUrl: hoseSourceUrl,
    }),
    part({
      id: 'reserve-tank', name: 'Coolant reserve tank', oemNumber: '19101-P2A-000',
      requirement: 'inspect', group: 'reservoir', note: 'Coolant reserve tank shown in the radiator-hose assembly.', sourceUrl: hoseSourceUrl,
    }),
    part({
      id: 'reserve-cap', name: 'Reserve tank cap assembly', oemNumber: '19102-P2A-000',
      requirement: 'normally-reusable', group: 'reservoir', note: 'Reserve-tank cap assembly.', sourceUrl: hoseSourceUrl,
    }),
    part({
      id: 'reserve-hose', name: 'Reserve tank hose (245 mm)', oemNumber: '19103-P08-000',
      requirement: 'inspect', group: 'hose', note: 'Overflow/reserve-tank hose.', sourceUrl: hoseSourceUrl,
    }),
  ];

  return {
    status: 'verified',
    generation: 6,
    generationLabel: CIVIC_SIXTH_GEN_LABEL,
    years: CIVIC_SIXTH_GEN_YEARS,
    configurationLabel,
    sourceUrl: input.sourceUrl,
    radiatorSourceUrl,
    hoseSourceUrl,
    radiatorNumber: radiator.number,
    alternateRadiatorNumbers: radiator.alternates,
    parts,
    note: 'Stage 1 publishes the front cooling/radiator assembly only. A/C, brakes, suspension and other blocks remain explicitly unavailable until their exact configuration data is verified.',
    researchQuery,
  };
}

export function sixthGenDefaultState(part: SixthGenPart): SixthGenPartState {
  if (part.id === 'radiator') return 'need';
  if (part.requirement === 'normally-reusable') return 'have';
  if (part.requirement === 'inspect') return 'inspect';
  return 'not-sure';
}
