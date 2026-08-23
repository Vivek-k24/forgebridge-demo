import {publishedHondaConfigurations} from '../data/hondaPublishedCoverage';
import {catalogConfigurations} from './hondaCatalogService';
import {hondaConfigurationConsumerLabel} from './hondaVehicleLabels';

export interface HondaManualConfiguration {
  /** Stable internal configuration identifier. Never shown as the trim label. */
  value: string;
  trim: string;
  label: string;
  secondary?: string;
  source: 'catalog' | 'partgraph-published';
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
 * Vehicle browsing uses the broad static Honda catalog. Repair coverage remains
 * a separate concern: selecting a catalog vehicle does not unlock a repair graph
 * unless PartGraph has verified that exact configuration.
 */
export async function fetchHondaManualConfigurations(year: number, model: string): Promise<HondaManualConfigurationResult> {
  try {
    const catalog = await catalogConfigurations(year, model);
    if (catalog.length) {
      const options = catalog.map((configuration) => ({
        value: configuration.key,
        trim: /hybrid/i.test(configuration.bodyTrim) ? 'Hybrid' : configuration.bodyTrim,
        label: configuration.bodyTrim,
        secondary: configuration.emissionTransmission,
        source: 'catalog' as const,
        sourceUrl: configuration.sourceUrl,
      }));

      return {
        options,
        sourceLabel: catalog[0].source,
        sourceUrl: catalog[0].sourceUrl,
        note: `${options.length} Honda catalog configuration${options.length === 1 ? '' : 's'} available for ${year} ${model}. Choose the body/trim and transmission that match the vehicle.`,
        fromCache: true,
      };
    }
  } catch {
    // Fall back to published PartGraph coverage if the static catalog cannot load.
  }

  const published = publishedHondaConfigurations(year, model);

  if (!published.length) {
    return {
      options: [],
      sourceLabel: 'PartGraph published Honda coverage',
      sourceUrl: 'https://techinfo.honda.com/rjanisis/logon.aspx',
      note: 'No Honda catalog configuration could be loaded for this year/model.',
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
    note: `Static catalog unavailable. Showing published repair coverage for ${year} ${model}.`,
    fromCache: true,
  };
}
