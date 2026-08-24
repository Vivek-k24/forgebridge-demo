import type {HondaModelOption} from './hondaVehicleService';

export interface HondaCatalogConfiguration {
  key: string;
  year: number;
  model: string;
  modelSlug: string;
  bodyTrim: string;
  bodyTrimSlug: string;
  emissionTransmission: string;
  emissionTransmissionSlug: string;
  configurationLabel: string;
  sourceUrl: string;
  source: string;
  market: string;
}

interface HondaCatalogYear {
  year: number;
  records: HondaCatalogConfiguration[];
}

const appBase =
  typeof window !== 'undefined' && window.location.pathname.startsWith('/forgebridge-demo/')
    ? '/forgebridge-demo/'
    : '/';
const dataRoot = `${appBase}data/honda`;
const yearPromises = new Map<number, Promise<HondaCatalogYear>>();

export const HONDA_CATALOG_FIRST_YEAR = 1996;
export const HONDA_CATALOG_LAST_YEAR = new Date().getFullYear();

// The source catalog contains destination/emission codes. For the North American
// consumer UI we keep the code families observed in U.S./Canada catalog context.
// Rows without a destination prefix are retained because many newer U.S. records
// are published simply as CVT/AT/MT. Fitment still depends on the exact source row.
const NORTH_AMERICA_DESTINATION_CODES = new Set(['KA', 'KC', 'KL', 'KR', 'KW']);

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {headers: {Accept: 'application/json'}});
  if (!response.ok) throw new Error(`PartGraph catalog request failed (${response.status}).`);
  return response.json() as Promise<T>;
}

function supportedYear(year: number): boolean {
  return year >= HONDA_CATALOG_FIRST_YEAR && year <= HONDA_CATALOG_LAST_YEAR;
}

function isNorthAmericaConfiguration(configuration: HondaCatalogConfiguration): boolean {
  const firstToken = configuration.emissionTransmission.trim().toUpperCase().split(/\s+/)[0] ?? '';
  if (!/^K[A-Z]$/.test(firstToken)) return true;
  return NORTH_AMERICA_DESTINATION_CODES.has(firstToken);
}

export function loadHondaCatalogYear(year: number): Promise<HondaCatalogYear> {
  if (!supportedYear(year)) {
    return Promise.resolve({year, records: []});
  }

  const cached = yearPromises.get(year);
  if (cached) return cached;

  const request = fetchJson<HondaCatalogYear>(`${dataRoot}/years/${year}.json`);
  yearPromises.set(year, request);
  return request;
}

export function catalogYears(): number[] {
  return Array.from(
    {length: HONDA_CATALOG_LAST_YEAR - HONDA_CATALOG_FIRST_YEAR + 1},
    (_, index) => HONDA_CATALOG_LAST_YEAR - index,
  );
}

export async function catalogModels(year: number): Promise<HondaModelOption[]> {
  const payload = await loadHondaCatalogYear(year);
  const models = [...new Set(
    payload.records
      .filter(isNorthAmericaConfiguration)
      .map((record) => record.model),
  )].sort((a, b) => a.localeCompare(b));

  return models.map((name, index) => ({id: index + 1, name}));
}

export async function catalogConfigurations(
  year: number,
  model: string,
): Promise<HondaCatalogConfiguration[]> {
  const payload = await loadHondaCatalogYear(year);
  const modelKey = model.trim().toLowerCase();

  return payload.records
    .filter((record) => record.model.toLowerCase() === modelKey)
    .filter(isNorthAmericaConfiguration)
    .sort((a, b) => a.configurationLabel.localeCompare(b.configurationLabel));
}
