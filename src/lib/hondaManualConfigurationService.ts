import {publishedHondaConfigurations} from '../data/hondaPublishedCoverage';
import {hondaConfigurationConsumerLabel} from './hondaVehicleLabels';

export interface HondaManualConfiguration {
  /** Stable internal configuration identifier. Never shown as the trim label. */
  value: string;
  trim: string;
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
 *
 * Important: raw catalog configuration labels remain internal provenance. The
 * dropdown is built from structured trim/body/engine/transmission fields.
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

  const options = published.map((configuration) => ({
    value: configuration.id,
    trim: configuration.trim,
    label: hondaConfigurationConsumerLabel(configuration),
    secondary: 'Exact repair graph available · Honda-published U.S. vehicle configuration',
    source: 'partgraph-published' as const,
    sourceUrl: configuration.vehicleSourceUrl,
  }));

  return {
    options,
    sourceLabel: published[0].vehicleSourceLabel,
    sourceUrl: published[0].vehicleSourceUrl,
    note: `Choose the trim you recognize from the vehicle badge or owner documentation. Current coverage: ${options[0].label}. Exact OEM part identity is checked against ${published[0].oemPartsSourceLabel}.`,
    fromCache: true,
  };
}
