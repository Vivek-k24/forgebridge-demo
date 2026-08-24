export interface HondaConsumerConfigurationLike {
  trim?: string;
  body?: string;
  engine?: string;
  transmission?: string;
}

export interface HondaConsumerIdentityLike {
  trim?: string;
  trim2?: string;
  series?: string;
  series2?: string;
  bodyClass?: string;
  doors?: string;
  displacementL?: string;
  transmissionStyle?: string;
}

const SUV_MODELS = new Set([
  'CR-V',
  'CR-V Hybrid',
  'Element',
  'HR-V',
  'Passport',
  'Pilot',
  'Prologue',
]);

const HATCHBACK_MODELS = new Set(['CR-Z', 'Fit', 'Fit EV']);

function clean(value: string | undefined): string {
  return value?.replace(/\s+/g, ' ').trim() ?? '';
}

function doorCount(body: string | undefined, doors?: string): number | null {
  const explicitDoors = clean(doors);
  if (/^\d+$/.test(explicitDoors)) return Number(explicitDoors);

  const match = clean(body).match(/\b(\d+)\s*[- ]?door\b/i);
  return match ? Number(match[1]) : null;
}

function doorLabel(body: string | undefined, doors?: string): string {
  const count = doorCount(body, doors);
  return count ? `${count} Door` : '';
}

function displacementLabel(engine: string | undefined, displacementL?: string): string {
  const engineMatch = clean(engine).match(/\b\d+(?:\.\d+)?\s*L\b/i);
  if (engineMatch) return engineMatch[0].replace(/\s+/g, '').toUpperCase();

  const displacement = clean(displacementL);
  if (!displacement || !/^\d+(?:\.\d+)?$/.test(displacement)) return '';
  return `${displacement}L`;
}

export function hondaTransmissionConsumerLabel(value: string | undefined): string {
  const transmission = clean(value);
  if (!transmission) return '';
  if (/\bCVT\b/i.test(transmission) || /continuously variable/i.test(transmission)) return 'CVT';
  if (/\b\d+AT\b/i.test(transmission) || /automatic/i.test(transmission)) return 'Automatic';
  if (/\b\d+MT\b/i.test(transmission) || /manual/i.test(transmission)) return 'Manual';
  return transmission;
}

/**
 * Body style is consumer-facing help only. It is never used for fitment.
 * We use model-family rules first, then conservative door-count rules for cars.
 */
export function hondaBodyStyleLabel(model: string, body: string | undefined, doors?: string): string {
  const normalizedModel = clean(model);
  const count = doorCount(body, doors);

  if (SUV_MODELS.has(normalizedModel)) return 'SUV';
  if (normalizedModel === 'Odyssey') return 'Minivan';
  if (normalizedModel === 'Ridgeline') return 'Pickup';
  if (normalizedModel === 'S2000') return 'Roadster';
  if (normalizedModel === 'Crosstour') return 'Crossover';
  if (HATCHBACK_MODELS.has(normalizedModel)) return 'Hatchback';
  if (normalizedModel === 'Del Sol' || normalizedModel === 'Prelude') return 'Coupe';

  if (normalizedModel === 'Civic') {
    if (count === 2) return 'Coupe';
    if (count === 3 || count === 5) return 'Hatchback';
    if (count === 4) return 'Sedan';
  }

  if (normalizedModel === 'Accord') {
    if (count === 2) return 'Coupe';
    if (count === 4) return 'Sedan';
    if (count === 5) return 'Wagon';
  }

  if (count === 2) return 'Coupe';
  if (count === 3) return 'Hatchback';
  return '';
}

export function hondaCatalogTrimBodyLabel(model: string, bodyTrim: string): string {
  const raw = clean(bodyTrim);
  const trim = raw.replace(/^\d+\s*[- ]?Door\s+/i, '').trim() || raw || 'Configuration';
  const bodyStyle = hondaBodyStyleLabel(model, raw);
  return bodyStyle ? `${trim} - ${bodyStyle}` : trim;
}

export function hondaGenerationNote(year: number, model: string): string {
  if (clean(model).toLowerCase() !== 'civic') return '';
  if (year >= 1996 && year <= 2000) return '6th generation Civic';
  if (year >= 2001 && year <= 2005) return '7th generation Civic';
  if (year >= 2006 && year <= 2011) return '8th generation Civic';
  if (year >= 2012 && year <= 2015) return '9th generation Civic';
  if (year >= 2016 && year <= 2021) return '10th generation Civic';
  if (year >= 2022) return '11th generation Civic';
  return '';
}

/**
 * Consumer labels must come from structured vehicle fields. Raw OEM/catalog
 * configuration strings remain provenance data and are intentionally not
 * parsed into fitment decisions.
 */
export function hondaConfigurationConsumerLabel(
  configuration: HondaConsumerConfigurationLike,
): string {
  const trim = clean(configuration.trim) || 'Configuration';
  const body = doorLabel(configuration.body);
  const engine = displacementLabel(configuration.engine);
  const transmission = hondaTransmissionConsumerLabel(configuration.transmission);
  const powertrain = [engine, transmission].filter(Boolean).join(' ');
  return [trim, body, powertrain].filter(Boolean).join(', ');
}

export function hondaIdentityConsumerLabel(identity: HondaConsumerIdentityLike): string {
  const trim =
    clean(identity.trim) ||
    clean(identity.trim2) ||
    clean(identity.series) ||
    clean(identity.series2) ||
    'Configuration';
  const body = doorLabel(identity.bodyClass, identity.doors);
  const engine = displacementLabel(undefined, identity.displacementL);
  const transmission = hondaTransmissionConsumerLabel(identity.transmissionStyle);
  const powertrain = [engine, transmission].filter(Boolean).join(' ');
  return [trim, body, powertrain].filter(Boolean).join(', ');
}
