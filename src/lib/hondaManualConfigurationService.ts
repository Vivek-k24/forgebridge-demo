import {publishedHondaConfigurations} from '../data/hondaPublishedCoverage';

export interface HondaManualConfiguration {
  value: string;
  label: string;
  secondary?: string;
  source: 'honda-official' | 'partgraph-published';
  sourceUrl: string;
}

export interface HondaManualConfigurationResult {
  options: HondaManualConfiguration[];
  sourceLabel: string;
  sourceUrl: string;
  note: string;
  fromCache: boolean;
}

/**
 * Consumer-facing vehicle selection is coverage-aware. We only offer a trim
 * after a PartGraph repair graph has been published for it. Broad vehicle/trim
 * discovery remains an admin/catalog-ingestion concern so the user never lands
 * on a dead Step 2.
 */
export async function fetchHondaManualConfigurations(year: number, model: string): Promise<HondaManualConfigurationResult> {
  const published = publishedHondaConfigurations(year, model);

  if (!published.length) {
    return {
      options: [],
      sourceLabel: 'PartGraph published Honda coverage',
      sourceUrl: 'https://techinfo.honda.com/rjanisis/logon.aspx',
      note: 'No consumer repair configuration is published for this year/model yet.',
      fromCache: true,
    };
  }

  return {
    options: published.map((configuration) => ({
      value: configuration.trim,
      label: configuration.trim,
      secondary: `${configuration.engine} · ${configuration.transmission} · ${configuration.market} market`,
      source: 'partgraph-published',
      sourceUrl: configuration.sourceUrl,
    })),
    sourceLabel: published[0].sourceLabel,
    sourceUrl: published[0].sourceUrl,
    note: `${published[0].catalogLabel} is the current published repair configuration. Honda ServiceExpress is the OEM authority; PartGraph exposes only configurations that have a reviewed graph instead of letting the repair flow dead-end.`,
    fromCache: true,
  };
}
