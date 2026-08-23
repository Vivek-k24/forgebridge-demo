export interface HondaManualConfiguration {
  value: string;
  label: string;
  secondary?: string;
  source: 'honda-official' | 'fueleconomy.gov';
  sourceUrl: string;
}

export interface HondaManualConfigurationResult {
  options: HondaManualConfiguration[];
  sourceLabel: string;
  sourceUrl: string;
  note: string;
  fromCache: boolean;
}

interface MenuItem {
  text: string;
  value: string;
}

const HONDA_2009_CIVIC_SEDAN_BROCHURE = 'https://automobiles.honda.com/images/2009/civic-sedan/downloads/2009-civic-sedan-brochure.pdf';
const FUEL_ECONOMY_DOCS = 'https://www.fueleconomy.gov/feg/ws/index.shtml';
const FUEL_ECONOMY_BASE = 'https://www.fueleconomy.gov/ws/rest/vehicle/menu';
const CACHE_TTL_MS = 30 * 24 * 60 * 60 * 1000;

const officialHondaManualCatalog: Record<string, HondaManualConfiguration[]> = {
  '2009:civic': [
    {value: 'DX', label: 'DX', secondary: '1.8L gasoline · 5-speed manual or automatic', source: 'honda-official', sourceUrl: HONDA_2009_CIVIC_SEDAN_BROCHURE},
    {value: 'DX-VP', label: 'DX-VP', secondary: '1.8L gasoline · sedan', source: 'honda-official', sourceUrl: HONDA_2009_CIVIC_SEDAN_BROCHURE},
    {value: 'LX', label: 'LX', secondary: '1.8L gasoline · sedan', source: 'honda-official', sourceUrl: HONDA_2009_CIVIC_SEDAN_BROCHURE},
    {value: 'LX-S', label: 'LX-S', secondary: '1.8L gasoline · sport-trim sedan', source: 'honda-official', sourceUrl: HONDA_2009_CIVIC_SEDAN_BROCHURE},
    {value: 'EX', label: 'EX', secondary: '1.8L gasoline · sedan', source: 'honda-official', sourceUrl: HONDA_2009_CIVIC_SEDAN_BROCHURE},
    {value: 'EX-L', label: 'EX-L', secondary: '1.8L gasoline · leather-trim sedan', source: 'honda-official', sourceUrl: HONDA_2009_CIVIC_SEDAN_BROCHURE},
    {value: 'Hybrid', label: 'Hybrid', secondary: '1.3L IMA hybrid · CVT', source: 'honda-official', sourceUrl: HONDA_2009_CIVIC_SEDAN_BROCHURE},
    {value: 'Si', label: 'Si', secondary: '2.0L gasoline · 6-speed manual', source: 'honda-official', sourceUrl: HONDA_2009_CIVIC_SEDAN_BROCHURE},
  ],
};

function catalogKey(year: number, model: string) {
  return `${year}:${model.trim().toLowerCase()}`;
}

function cacheKey(year: number, model: string) {
  return `partgraph.honda.manual-config.${catalogKey(year, model)}.v1`;
}

function readCache(year: number, model: string): HondaManualConfigurationResult | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(cacheKey(year, model));
    if (!raw) return null;
    const cached = JSON.parse(raw) as {savedAt: number; result: HondaManualConfigurationResult};
    if (!cached.result || Date.now() - cached.savedAt > CACHE_TTL_MS) return null;
    return {...cached.result, fromCache: true};
  } catch {
    return null;
  }
}

function writeCache(year: number, model: string, result: HondaManualConfigurationResult) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(cacheKey(year, model), JSON.stringify({savedAt: Date.now(), result}));
  } catch {
    // Private browsing or storage policy can disable localStorage. The lookup still works without persistence.
  }
}

function normalizedModel(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

function isRelatedFuelEconomyModel(candidate: string, selectedModel: string) {
  const candidateNormalized = normalizedModel(candidate);
  const selectedNormalized = normalizedModel(selectedModel);
  return candidateNormalized === selectedNormalized || candidateNormalized.startsWith(`${selectedNormalized} `);
}

function parseMenuItems(xml: string): MenuItem[] {
  const document = new DOMParser().parseFromString(xml, 'application/xml');
  if (document.querySelector('parsererror')) throw new Error('FuelEconomy.gov returned unreadable vehicle data.');
  return [...document.querySelectorAll('menuItem')]
    .map((node) => ({
      text: node.querySelector('text')?.textContent?.trim() ?? '',
      value: node.querySelector('value')?.textContent?.trim() ?? '',
    }))
    .filter((item) => item.text && item.value);
}

async function fetchMenu(path: string, params: Record<string, string | number>): Promise<MenuItem[]> {
  const query = new URLSearchParams(Object.entries(params).map(([key, value]) => [key, String(value)]));
  const response = await fetch(`${FUEL_ECONOMY_BASE}/${path}?${query.toString()}`, {
    headers: {Accept: 'application/xml'},
  });
  if (!response.ok) throw new Error(`FuelEconomy.gov request failed (${response.status}).`);
  return parseMenuItems(await response.text());
}

function dedupe(options: HondaManualConfiguration[]) {
  const seen = new Set<string>();
  return options.filter((option) => {
    const key = option.value.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export async function fetchHondaManualConfigurations(year: number, model: string): Promise<HondaManualConfigurationResult> {
  const official = officialHondaManualCatalog[catalogKey(year, model)];
  if (official) {
    return {
      options: official,
      sourceLabel: 'American Honda · 2009 Civic Sedan brochure',
      sourceUrl: HONDA_2009_CIVIC_SEDAN_BROCHURE,
      note: 'Honda-published trim names are used for the repair-supported 2009 Civic Sedan.',
      fromCache: false,
    };
  }

  const cached = readCache(year, model);
  if (cached) return cached;

  if (year < 1984) {
    return {
      options: [],
      sourceLabel: 'Manual model selection',
      sourceUrl: FUEL_ECONOMY_DOCS,
      note: 'FuelEconomy.gov vehicle configurations begin with model year 1984. VIN lookup remains available as an optional second path for 1981–1983 vehicles.',
      fromCache: false,
    };
  }

  try {
    const models = await fetchMenu('model', {year, make: 'Honda'});
    const relatedModels = models.filter((item) => isRelatedFuelEconomyModel(item.value, model)).slice(0, 8);
    const targets = relatedModels.length ? relatedModels : [{text: model, value: model}];

    const optionGroups = await Promise.all(targets.map(async (variant) => ({
      variant: variant.value,
      options: await fetchMenu('options', {year, make: 'Honda', model: variant.value}),
    })));

    const options = dedupe(optionGroups.flatMap(({variant, options: menuOptions}) => menuOptions.map((item) => {
      const label = normalizedModel(variant) === normalizedModel(model)
        ? item.text
        : `${variant} · ${item.text}`;
      return {
        value: label,
        label,
        secondary: `EPA/DOE vehicle configuration · vehicle ID ${item.value}`,
        source: 'fueleconomy.gov' as const,
        sourceUrl: FUEL_ECONOMY_DOCS,
      };
    })));

    const result: HondaManualConfigurationResult = {
      options,
      sourceLabel: 'FuelEconomy.gov · U.S. EPA / Department of Energy',
      sourceUrl: FUEL_ECONOMY_DOCS,
      note: options.length
        ? 'Public configuration data fills the manual path without requiring a VIN. EPA configurations can combine powertrain/drive variants and are not always identical to Honda marketing trim names.'
        : 'The public EPA/DOE menu did not expose a finer configuration for this model. The model can still be selected manually; exact repair data remains gated by PartGraph coverage.',
      fromCache: false,
    };
    writeCache(year, model, result);
    return result;
  } catch {
    return {
      options: [],
      sourceLabel: 'FuelEconomy.gov · U.S. EPA / Department of Energy',
      sourceUrl: FUEL_ECONOMY_DOCS,
      note: 'Public configuration lookup is temporarily unavailable. Manual year/model selection still works; VIN remains an optional second path, not a requirement.',
      fromCache: false,
    };
  }
}
