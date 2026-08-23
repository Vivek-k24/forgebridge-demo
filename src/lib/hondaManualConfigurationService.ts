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
      sourceUrl: configuration.vehicleSourceUrl,
    })),
    sourceLabel: published[0].vehicleSourceLabel,
    sourceUrl: published[0].vehicleSourceUrl,
    note: `${published[0].catalogLabel} is the current published repair configuration. The vehicle identity is Honda-published; ${published[0].oemPartsSourceLabel} is the OEM parts authority used by the offline ingestion/review pipeline.`,
    fromCache: true,
  };
}
