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

interface HondaCatalogIndex {
  schemaVersion: number;
  source: string;
  sourceRoot: string;
  generatedAt: string;
  recordCount: number;
  yearCount: number;
  modelCount: number;
  years: number[];
  modelsByYear: Record<string, string[]>;
  yearsByModel: Record<string, number[]>;
  identityRule: string;
  runtimeLlmTokens: number;
}

interface HondaCatalogYear {
  year: number;
  records: HondaCatalogConfiguration[];
}

const dataRoot = `${import.meta.env.BASE_URL}data/honda`;
let indexPromise: Promise<HondaCatalogIndex> | null = null;
const yearPromises = new Map<number, Promise<HondaCatalogYear>>();

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {headers: {Accept: 'application/json'}});
  if (!response.ok) throw new Error(`PartGraph catalog request failed (${response.status}).`);
  return response.json() as Promise<T>;
}

export function loadHondaCatalogIndex(): Promise<HondaCatalogIndex> {
  if (!indexPromise) indexPromise = fetchJson<HondaCatalogIndex>(`${dataRoot}/catalog-index.json`);
  return indexPromise;
}

export function loadHondaCatalogYear(year: number): Promise<HondaCatalogYear> {
  const cached = yearPromises.get(year);
  if (cached) return cached;
  const request = fetchJson<HondaCatalogYear>(`${dataRoot}/years/${year}.json`);
  yearPromises.set(year, request);
  return request;
}

export async function catalogYears(): Promise<number[]> {
  const index = await loadHondaCatalogIndex();
  return [...index.years].sort((a, b) => b - a);
}

export async function catalogModels(year: number): Promise<HondaModelOption[]> {
  const index = await loadHondaCatalogIndex();
  return (index.modelsByYear[String(year)] ?? []).map((name, indexValue) => ({id: indexValue + 1, name}));
}

export async function catalogConfigurations(year: number, model: string): Promise<HondaCatalogConfiguration[]> {
  const payload = await loadHondaCatalogYear(year);
  return payload.records
    .filter((record) => record.model.toLowerCase() === model.trim().toLowerCase())
    .sort((a, b) => a.configurationLabel.localeCompare(b.configurationLabel));
}

export async function catalogStats() {
  const index = await loadHondaCatalogIndex();
  return {
    generatedAt: index.generatedAt,
    recordCount: index.recordCount,
    yearCount: index.yearCount,
    modelCount: index.modelCount,
    runtimeLlmTokens: index.runtimeLlmTokens,
  };
}
