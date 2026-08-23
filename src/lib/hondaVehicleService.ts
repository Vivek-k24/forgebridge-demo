export type VehicleSelectionSource = 'demo' | 'manual' | 'nhtsa-vin';

export interface HondaModelOption {
  id: number;
  name: string;
}

export interface HondaVehicleIdentity {
  source: VehicleSelectionSource;
  vin?: string;
  make: 'Honda';
  year: number;
  model: string;
  trim?: string;
  trim2?: string;
  series?: string;
  series2?: string;
  bodyClass?: string;
  vehicleType?: string;
  doors?: string;
  driveType?: string;
  fuelTypePrimary?: string;
  fuelTypeSecondary?: string;
  electrificationLevel?: string;
  engineCylinders?: string;
  displacementL?: string;
  engineModel?: string;
  engineManufacturer?: string;
  transmissionStyle?: string;
  transmissionSpeeds?: string;
  plantCity?: string;
  plantState?: string;
  plantCountry?: string;
  destinationMarket?: string;
  nhtsaErrorCode?: string;
  nhtsaErrorText?: string;
}

interface NhtsaResponse<T> {
  Count?: number;
  Message?: string;
  Results?: T[];
}

interface NhtsaModelResult {
  Make_ID?: number;
  Make_Name?: string;
  Model_ID?: number;
  Model_Name?: string;
}

type NhtsaVinResult = Record<string, string> & {
  VIN?: string;
  Make?: string;
  Model?: string;
  ModelYear?: string;
  Trim?: string;
  Trim2?: string;
  Series?: string;
  Series2?: string;
  BodyClass?: string;
  VehicleType?: string;
  Doors?: string;
  DriveType?: string;
  FuelTypePrimary?: string;
  FuelTypeSecondary?: string;
  ElectrificationLevel?: string;
  EngineCylinders?: string;
  DisplacementL?: string;
  EngineModel?: string;
  EngineManufacturer?: string;
  TransmissionStyle?: string;
  TransmissionSpeeds?: string;
  PlantCity?: string;
  PlantState?: string;
  PlantCountry?: string;
  DestinationMarket?: string;
  ErrorCode?: string;
  ErrorText?: string;
};

const NHTSA_BASE = 'https://vpic.nhtsa.dot.gov/api/vehicles';
const MODEL_CACHE_TTL_MS = 30 * 24 * 60 * 60 * 1000;
const modelMemoryCache = new Map<number, HondaModelOption[]>();
const vinMemoryCache = new Map<string, HondaVehicleIdentity>();

const fallbackHondaAutomobileModels = [
  'Accord',
  'Civic',
  'CR-V',
  'HR-V',
  'Pilot',
  'Passport',
  'Odyssey',
  'Ridgeline',
  'Fit',
  'Insight',
  'S2000',
  'Prelude',
  'CR-X',
  'del Sol',
  'Element',
  'Crosstour',
  'CR-Z',
  'Clarity',
  'Prologue',
] as const;

export const hondaTrimSuggestions = [
  'Base',
  'CX',
  'DX',
  'DX-VP',
  'EX',
  'EX-L',
  'EX-L Navi',
  'EX-T',
  'GX',
  'HF',
  'HX',
  'Hybrid',
  'Hybrid-L',
  'LX',
  'LX-P',
  'LX-S',
  'SE',
  'Si',
  'Sport',
  'Sport Hybrid',
  'Sport-L',
  'Sport-L Hybrid',
  'Touring',
  'Touring Hybrid',
  'Type R',
  'Elite',
  'TrailSport',
  'Black Edition',
  'RTL',
  'RTL-T',
  'RTL-E',
  'Sport Touring',
  'Sport Touring Hybrid',
  'Value Package',
  'MX Hybrid',
] as const;

export const demoHondaIdentity: HondaVehicleIdentity = {
  source: 'demo',
  make: 'Honda',
  year: 2009,
  model: 'Civic',
  trim: 'MX Hybrid',
  series: 'Civic Hybrid',
  bodyClass: 'Sedan/Saloon',
  vehicleType: 'PASSENGER CAR',
  doors: '4',
  driveType: '4x2',
  fuelTypePrimary: 'Gasoline',
  fuelTypeSecondary: 'Electric',
  electrificationLevel: 'Hybrid Electric Vehicle (HEV)',
  engineCylinders: '4',
  displacementL: '1.3',
  transmissionStyle: 'Continuously Variable Transmission (CVT)',
};

export function hondaModelYears(): number[] {
  const latest = new Date().getFullYear() + 1;
  const years: number[] = [];
  for (let year = latest; year >= 1981; year -= 1) years.push(year);
  return years;
}

export function normalizeVin(value: string): string {
  return value.toUpperCase().replace(/[^A-HJ-NPR-Z0-9]/g, '').slice(0, 17);
}

export function isCompleteVin(value: string): boolean {
  return /^[A-HJ-NPR-Z0-9]{17}$/.test(normalizeVin(value));
}

function cacheKeyForModels(year: number) {
  return `partgraph.honda.models.${year}.v1`;
}

function readModelCache(year: number): HondaModelOption[] | null {
  const memory = modelMemoryCache.get(year);
  if (memory) return memory;
  if (typeof window === 'undefined') return null;

  try {
    const raw = window.localStorage.getItem(cacheKeyForModels(year));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as {savedAt: number; models: HondaModelOption[]};
    if (!Array.isArray(parsed.models) || Date.now() - parsed.savedAt > MODEL_CACHE_TTL_MS) return null;
    modelMemoryCache.set(year, parsed.models);
    return parsed.models;
  } catch {
    return null;
  }
}

function writeModelCache(year: number, models: HondaModelOption[]) {
  modelMemoryCache.set(year, models);
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(cacheKeyForModels(year), JSON.stringify({savedAt: Date.now(), models}));
  } catch {
    // Local storage can be unavailable in strict privacy modes. The in-memory cache still works.
  }
}

function dedupeModels(results: NhtsaModelResult[]): HondaModelOption[] {
  const byName = new Map<string, HondaModelOption>();
  for (const result of results) {
    const name = result.Model_Name?.trim();
    if (!name) continue;
    const key = name.toLowerCase();
    if (!byName.has(key)) byName.set(key, {id: result.Model_ID ?? 0, name});
  }
  return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name));
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {headers: {Accept: 'application/json'}});
  if (!response.ok) throw new Error(`NHTSA request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export async function fetchHondaModels(year: number): Promise<{models: HondaModelOption[]; yearScoped: boolean; fromCache: boolean}> {
  const cached = readModelCache(year);
  if (cached) return {models: cached, yearScoped: year >= 1996, fromCache: true};

  if (year < 1996) {
    const models = fallbackHondaAutomobileModels.map((name, index) => ({id: index + 1, name}));
    writeModelCache(year, models);
    return {models, yearScoped: false, fromCache: false};
  }

  const vehicleTypes = ['Passenger Car', 'Multipurpose Passenger Vehicle (MPV)', 'Truck'];
  try {
    const responses = await Promise.all(
      vehicleTypes.map((vehicleType) => {
        const url = `${NHTSA_BASE}/GetModelsForMakeYear/make/honda/modelyear/${year}/vehicletype/${encodeURIComponent(vehicleType)}?format=json`;
        return fetchJson<NhtsaResponse<NhtsaModelResult>>(url);
      }),
    );
    const models = dedupeModels(responses.flatMap((response) => response.Results ?? []));
    if (!models.length) throw new Error('NHTSA returned no Honda automobile models for this year.');
    writeModelCache(year, models);
    return {models, yearScoped: true, fromCache: false};
  } catch {
    const models = fallbackHondaAutomobileModels.map((name, index) => ({id: index + 1, name}));
    writeModelCache(year, models);
    return {models, yearScoped: false, fromCache: false};
  }
}

function text(value: string | undefined) {
  const normalized = value?.trim();
  return normalized || undefined;
}

export async function decodeHondaVin(rawVin: string): Promise<HondaVehicleIdentity> {
  const vin = normalizeVin(rawVin);
  if (!isCompleteVin(vin)) throw new Error('Enter a complete 17-character VIN. Letters I, O and Q are not valid VIN characters.');

  const cached = vinMemoryCache.get(vin);
  if (cached) return cached;

  const url = `${NHTSA_BASE}/DecodeVinValuesExtended/${encodeURIComponent(vin)}?format=json`;
  const response = await fetchJson<NhtsaResponse<NhtsaVinResult>>(url);
  const result = response.Results?.[0];
  if (!result) throw new Error('NHTSA did not return a VIN result.');

  const make = text(result.Make);
  if (!make || make.toLowerCase() !== 'honda') {
    throw new Error(make ? `This VIN decodes as ${make}, not Honda.` : 'NHTSA could not verify this VIN as a Honda.');
  }

  const year = Number.parseInt(result.ModelYear ?? '', 10);
  const model = text(result.Model);
  if (!Number.isFinite(year) || !model) {
    throw new Error(result.ErrorText || 'NHTSA could not resolve the model year and model from this VIN.');
  }

  const identity: HondaVehicleIdentity = {
    source: 'nhtsa-vin',
    vin,
    make: 'Honda',
    year,
    model,
    trim: text(result.Trim),
    trim2: text(result.Trim2),
    series: text(result.Series),
    series2: text(result.Series2),
    bodyClass: text(result.BodyClass),
    vehicleType: text(result.VehicleType),
    doors: text(result.Doors),
    driveType: text(result.DriveType),
    fuelTypePrimary: text(result.FuelTypePrimary),
    fuelTypeSecondary: text(result.FuelTypeSecondary),
    electrificationLevel: text(result.ElectrificationLevel),
    engineCylinders: text(result.EngineCylinders),
    displacementL: text(result.DisplacementL),
    engineModel: text(result.EngineModel),
    engineManufacturer: text(result.EngineManufacturer),
    transmissionStyle: text(result.TransmissionStyle),
    transmissionSpeeds: text(result.TransmissionSpeeds),
    plantCity: text(result.PlantCity),
    plantState: text(result.PlantState),
    plantCountry: text(result.PlantCountry),
    destinationMarket: text(result.DestinationMarket),
    nhtsaErrorCode: text(result.ErrorCode),
    nhtsaErrorText: text(result.ErrorText),
  };

  vinMemoryCache.set(vin, identity);
  return identity;
}

export function manualHondaIdentity(year: number, model: string, trim: string): HondaVehicleIdentity {
  return {
    source: 'manual',
    make: 'Honda',
    year,
    model: model.trim(),
    trim: trim.trim() || undefined,
  };
}

export function identityTrimLabel(identity: HondaVehicleIdentity): string {
  return identity.trim || identity.trim2 || identity.series || identity.series2 || 'Trim not verified';
}

export function identityEngineLabel(identity: HondaVehicleIdentity): string {
  const bits = [identity.displacementL ? `${identity.displacementL}L` : '', identity.engineCylinders ? `${identity.engineCylinders}-cyl` : '', identity.electrificationLevel || '']
    .filter(Boolean);
  return bits.join(' · ') || identity.engineModel || 'Engine not reported';
}

export function hasVerifiedDemoCoverage(identity: HondaVehicleIdentity): boolean {
  if (identity.year !== 2009 || identity.model.trim().toLowerCase() !== 'civic') return false;
  const clues = [
    identity.trim,
    identity.trim2,
    identity.series,
    identity.series2,
    identity.electrificationLevel,
    identity.engineModel,
    identity.displacementL,
  ]
    .filter((value): value is string => Boolean(value))
    .join(' ')
    .toLowerCase();

  return clues.includes('hybrid') || clues.includes('1.3');
}
