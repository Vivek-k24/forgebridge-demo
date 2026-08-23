export interface HondaPublishedConfiguration {
  id: string;
  year: number;
  model: string;
  trim: string;
  aliases: string[];
  market: 'US';
  body: string;
  engine: string;
  transmission: string;
  catalogLabel: string;
  sourceLabel: string;
  sourceUrl: string;
  sourceGuideUrl: string;
}

export const hondaPublishedConfigurations: HondaPublishedConfiguration[] = [
  {
    id: 'honda-civic-2009-hybrid-us',
    year: 2009,
    model: 'Civic',
    trim: 'Hybrid',
    aliases: ['Hybrid', 'Hybrid-L', 'MX Hybrid', '4DR MX HYBRID', 'Civic Hybrid'],
    market: 'US',
    body: '4-door sedan',
    engine: '1.3L I4 gasoline-electric hybrid',
    transmission: 'CVT',
    catalogLabel: '2009 Honda Civic · 4DR MX HYBRID · KA CVT',
    sourceLabel: 'American Honda ServiceExpress parts catalog',
    sourceUrl: 'https://techinfo.honda.com/rjanisis/logon.aspx',
    sourceGuideUrl: 'https://techinfo.honda.com/rjanisis/pubs/Web/SvcExp_QS.pdf',
  },
];

function normalized(value: string | undefined) {
  return (value ?? '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

export function publishedHondaYears(): number[] {
  return [...new Set(hondaPublishedConfigurations.map((item) => item.year))].sort((a, b) => b - a);
}

export function publishedHondaModels(year: number): string[] {
  return [...new Set(
    hondaPublishedConfigurations
      .filter((item) => item.year === year)
      .map((item) => item.model),
  )].sort((a, b) => a.localeCompare(b));
}

export function publishedHondaConfigurations(year: number, model: string): HondaPublishedConfiguration[] {
  const modelKey = normalized(model);
  return hondaPublishedConfigurations.filter(
    (item) => item.year === year && normalized(item.model) === modelKey,
  );
}

export function findPublishedHondaConfiguration(input: {
  year: number;
  model: string;
  trim?: string;
  trim2?: string;
  series?: string;
  series2?: string;
  fuelTypePrimary?: string;
  fuelTypeSecondary?: string;
  electrificationLevel?: string;
  engineModel?: string;
  displacementL?: string;
  transmissionStyle?: string;
}): HondaPublishedConfiguration | null {
  const candidates = publishedHondaConfigurations(input.year, input.model);
  if (!candidates.length) return null;

  const clues = [
    input.trim,
    input.trim2,
    input.series,
    input.series2,
    input.fuelTypePrimary,
    input.fuelTypeSecondary,
    input.electrificationLevel,
    input.engineModel,
    input.displacementL,
    input.transmissionStyle,
  ]
    .filter((value): value is string => Boolean(value))
    .map(normalized)
    .join(' ');

  for (const candidate of candidates) {
    const aliasMatch = candidate.aliases.some((alias) => {
      const aliasKey = normalized(alias);
      return aliasKey && clues.includes(aliasKey);
    });
    const hybridPowertrainMatch = clues.includes('hybrid') || clues.includes('electric') || clues.includes('1 3');
    if (aliasMatch || (normalized(candidate.trim).includes('hybrid') && hybridPowertrainMatch)) return candidate;
  }

  return null;
}
