import {publishedHondaConfigurations} from '../data/hondaPublishedCoverage';
import {catalogConfigurations} from './hondaCatalogService';
import {
  hondaCatalogTrimBodyLabel,
  hondaConfigurationConsumerLabel,
  hondaTransmissionConsumerLabel,
} from './hondaVehicleLabels';

export interface HondaManualConfiguration {
  /** Stable internal configuration identifier. Never shown as the trim label. */
  value: string;
  trim: string;
  label: string;
  secondary?: string;
  bodyStyle?: string;
  bodyTrim: string;
  emissionTransmission: string;
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
 * separate: selecting a catalog vehicle never unlocks a repair map unless that
 * exact configuration has verified PartGraph data.
 */
export async function fetchHondaManualConfigurations(
  year: number,
  model: string,
): Promise<HondaManualConfigurationResult> {
  try {
    const catalog = await catalogConfigurations(year, model);
    if (catalog.length) {
      const options = catalog.map((configuration) => ({
        value: configuration.key,
        trim: configuration.bodyTrim.replace(/^\d+\s*[- ]?Door\s+/i, '').trim(),
        label: hondaCatalogTrimBodyLabel(model, configuration.bodyTrim),
        secondary: hondaTransmissionConsumerLabel(configuration.emissionTransmission),
        bodyTrim: configuration.bodyTrim,
        emissionTransmission: configuration.emissionTransmission,
        source: 'catalog' as const,
        sourceUrl: configuration.sourceUrl,
      }));

      return {
        options,
        sourceLabel: catalog[0].source,
        sourceUrl: catalog[0].sourceUrl,
        note: `${options.length} North American catalog configuration${options.length === 1 ? '' : 's'} available for ${year} ${model}.`,
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
      sourceLabel: 'PartGraph Honda coverage',
      sourceUrl: 'https://techinfo.honda.com/rjanisis/logon.aspx',
      note: 'No U.S./Canada Honda configuration could be loaded for this year and model.',
      fromCache: true,
    };
  }

  const options = published.map((configuration) => ({
    value: configuration.id,
    trim: configuration.trim,
    label: hondaConfigurationConsumerLabel(configuration),
    secondary: hondaTransmissionConsumerLabel(configuration.transmission),
    bodyTrim: configuration.body,
    emissionTransmission: configuration.transmission,
    source: 'partgraph-published' as const,
    sourceUrl: configuration.vehicleSourceUrl,
  }));

  return {
    options,
    sourceLabel: published[0].vehicleSourceLabel,
    sourceUrl: published[0].vehicleSourceUrl,
    note: `Showing verified PartGraph coverage for ${year} ${model}.`,
    fromCache: true,
  };
}
