import {
  findPublishedHondaConfiguration,
  publishedHondaModels,
} from '../data/hondaPublishedCoverage';
import {
  catalogModels,
  catalogYears,
  HONDA_CATALOG_FIRST_YEAR,
  HONDA_CATALOG_LAST_YEAR,
} from './hondaCatalogService';
import {
  hondaConfigurationConsumerLabel,
  hondaIdentityConsumerLabel,
} from './hondaVehicleLabels';

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
const vinMemoryCache = new Map<string, HondaVehicleIdentity>();

export const hondaTrimSuggestions = ['Hybrid', 'MX Hybrid', 'Hybrid-L'] as const;

export const demoHondaIdentity: HondaVehicleIdentity = {
  source: 'demo',
  make: 'Honda',
  year: 2009,
  model: 'Civic',
  trim: 'Hybrid',
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
  return catalogYears();
}

export function normalizeVin(value: string): string {
  return value.toUpperCase().replace(/[^A-HJ-NPR-Z0-9]/g, '').slice(0, 17);
}

export function isCompleteVin(value: string): boolean {
  return /^[A-HJ-NPR-Z0-9]{17}$/.test(normalizeVin(value));
}

export async function fetchHondaModels(
  year: number,
): Promise<{models: HondaModelOption[]; yearScoped: boolean; fromCache: boolean}> {
  if (year < HONDA_CATALOG_FIRST_YEAR || year > HONDA_CATALOG_LAST_YEAR) {
    return {models: [], yearScoped: true, fromCache: true};
  }

  try {
    const models = await catalogModels(year);
    if (models.length) return {models, yearScoped: true, fromCache: true};
  } catch {
    // Fall through to the much smaller published repair coverage list.
  }

  const models = publishedHondaModels(year).map((name, index) => ({
    id: index + 1,
    name,
  }));
  return {models, yearScoped: true, fromCache: true};
}

function text(value: string | undefined) {
  const normalized = value?.trim();
  return normalized || undefined;
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {headers: {Accept: 'application/json'}});
  if (!response.ok) throw new Error(`NHTSA request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export async function decodeHondaVin(rawVin: string): Promise<HondaVehicleIdentity> {
  const vin = normalizeVin(rawVin);
  if (!isCompleteVin(vin)) {
    throw new Error(
      'Enter a complete 17-character VIN. Letters I, O and Q are not valid VIN characters.',
    );
  }

  const cached = vinMemoryCache.get(vin);
  if (cached) return cached;

  const url = `${NHTSA_BASE}/DecodeVinValuesExtended/${encodeURIComponent(vin)}?format=json`;
  const response = await fetchJson<NhtsaResponse<NhtsaVinResult>>(url);
  const result = response.Results?.[0];
  if (!result) throw new Error('NHTSA did not return a VIN result.');

  const make = text(result.Make);
  if (!make || make.toLowerCase() !== 'honda') {
    throw new Error(
      make ? `This VIN decodes as ${make}, not Honda.` : 'NHTSA could not verify this VIN as a Honda.',
    );
  }

  const year = Number.parseInt(result.ModelYear ?? '', 10);
  const model = text(result.Model);
  if (!Number.isFinite(year) || !model) {
    throw new Error(result.ErrorText || 'NHTSA could not resolve the model year and model from this VIN.');
  }

  if (year < HONDA_CATALOG_FIRST_YEAR || year > HONDA_CATALOG_LAST_YEAR) {
    throw new Error(
      `PartGraph currently supports Honda model years ${HONDA_CATALOG_FIRST_YEAR}–${HONDA_CATALOG_LAST_YEAR}.`,
    );
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

  if (!findPublishedHondaConfiguration(identity)) {
    throw new Error(
      'This Honda is identified, but PartGraph does not have a verified repair map for this exact vehicle yet.',
    );
  }

  vinMemoryCache.set(vin, identity);
  return identity;
}

export function manualHondaIdentity(
  year: number,
  model: string,
  trim: string,
): HondaVehicleIdentity {
  return {
    source: 'manual',
    make: 'Honda',
    year,
    model: model.trim(),
    trim: trim.trim() || undefined,
  };
}

export function identityTrimLabel(identity: HondaVehicleIdentity): string {
  const published = findPublishedHondaConfiguration(identity);
  if (published) return hondaConfigurationConsumerLabel(published);
  return hondaIdentityConsumerLabel(identity);
}

export function identityEngineLabel(identity: HondaVehicleIdentity): string {
  const bits = [
    identity.displacementL ? `${identity.displacementL}L` : '',
    identity.engineCylinders ? `${identity.engineCylinders}-cyl` : '',
    identity.electrificationLevel || '',
  ].filter(Boolean);
  return bits.join(' · ') || identity.engineModel || 'Engine not reported';
}

export function is2009CivicCandidate(identity: HondaVehicleIdentity): boolean {
  return identity.year === 2009 && identity.model.trim().toLowerCase() === 'civic';
}

export function hasVerifiedDemoCoverage(identity: HondaVehicleIdentity): boolean {
  return Boolean(findPublishedHondaConfiguration(identity));
}
