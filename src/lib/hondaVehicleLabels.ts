export interface HondaConsumerConfigurationLike {
  trim?: string;
  body?: string;
  engine?: string;
  transmission?: string;
}

export interface HondaConsumerIdentityLike {
  trim?: string;
  trim2?: string;
  series?: string;
  series2?: string;
  bodyClass?: string;
  doors?: string;
  displacementL?: string;
  transmissionStyle?: string;
}

function clean(value: string | undefined): string {
  return value?.replace(/\s+/g, ' ').trim() ?? '';
}

function doorLabel(body: string | undefined, doors?: string): string {
  const explicitDoors = clean(doors).match(/^\d+$/)?.[0];
  if (explicitDoors) return `${explicitDoors} Door`;

  const match = clean(body).match(/\b(\d+)\s*[- ]?door\b/i);
  return match ? `${match[1]} Door` : '';
}

function displacementLabel(engine: string | undefined, displacementL?: string): string {
  const engineMatch = clean(engine).match(/\b\d+(?:\.\d+)?\s*L\b/i);
  if (engineMatch) return engineMatch[0].replace(/\s+/g, '').toUpperCase();

  const displacement = clean(displacementL);
  if (!displacement || !/^\d+(?:\.\d+)?$/.test(displacement)) return '';
  return `${displacement}L`;
}

function transmissionLabel(value: string | undefined): string {
  const transmission = clean(value);
  if (!transmission) return '';
  if (/\bCVT\b/i.test(transmission) || /continuously variable/i.test(transmission)) return 'CVT transmission';
  if (/automatic/i.test(transmission)) return 'Automatic transmission';
  if (/manual/i.test(transmission)) return 'Manual transmission';
  return /transmission/i.test(transmission) ? transmission : `${transmission} transmission`;
}

/**
 * Consumer labels must come from structured vehicle fields. Raw OEM/catalog
 * configuration strings remain provenance data and are intentionally not
 * parsed into user-facing trim names.
 */
export function hondaConfigurationConsumerLabel(configuration: HondaConsumerConfigurationLike): string {
  const trim = clean(configuration.trim) || 'Configuration';
  const body = doorLabel(configuration.body);
  const engine = displacementLabel(configuration.engine);
  const transmission = transmissionLabel(configuration.transmission);
  const powertrain = [engine, transmission].filter(Boolean).join(' ');
  return [trim, body, powertrain].filter(Boolean).join(', ');
}

export function hondaIdentityConsumerLabel(identity: HondaConsumerIdentityLike): string {
  const trim = clean(identity.trim) || clean(identity.trim2) || clean(identity.series) || clean(identity.series2) || 'Configuration';
  const body = doorLabel(identity.bodyClass, identity.doors);
  const engine = displacementLabel(undefined, identity.displacementL);
  const transmission = transmissionLabel(identity.transmissionStyle);
  const powertrain = [engine, transmission].filter(Boolean).join(' ');
  return [trim, body, powertrain].filter(Boolean).join(', ');
}
