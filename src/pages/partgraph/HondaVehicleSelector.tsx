import {useEffect, useMemo, useState} from 'react';
import {
  AlertTriangle,
  CarFront,
  CheckCircle2,
  Database,
  ExternalLink,
  LoaderCircle,
  ScanLine,
  ShieldCheck,
} from 'lucide-react';
import {
  catalogConfigurations,
  catalogModels,
  catalogStats,
  catalogYears,
  type HondaCatalogConfiguration,
} from '../../lib/hondaCatalogService';
import {
  decodeHondaVin,
  demoHondaIdentity,
  fetchHondaModels,
  hondaModelYears,
  identityEngineLabel,
  identityTrimLabel,
  isCompleteVin,
  manualHondaIdentity,
  normalizeVin,
  type HondaModelOption,
  type HondaVehicleIdentity,
} from '../../lib/hondaVehicleService';

type FinderMode = 'catalog' | 'vin';

type CatalogHondaVehicleIdentity = HondaVehicleIdentity & {
  catalogVerified?: boolean;
  catalogKey?: string;
  catalogSourceUrl?: string;
  bodyTrim?: string;
  emissionTransmission?: string;
};

interface HondaVehicleSelectorProps {
  value: CatalogHondaVehicleIdentity;
  onChange: (identity: HondaVehicleIdentity) => void;
}

function Identifier({label, value}: {label: string; value?: string}) {
  if (!value) return null;
  return (
    <div className="pg-id-fact">
      <small>{label}</small>
      <strong>{value}</strong>
    </div>
  );
}

export function HondaVehicleSelector({value, onChange}: HondaVehicleSelectorProps) {
  const [mode, setMode] = useState<FinderMode>(value.source === 'nhtsa-vin' ? 'vin' : 'catalog');
  const [vin, setVin] = useState(value.vin ?? '');
  const [year, setYear] = useState(value.year);
  const [model, setModel] = useState(value.model);
  const [configurationKey, setConfigurationKey] = useState(value.catalogKey ?? '');
  const [years, setYears] = useState<number[]>([]);
  const [models, setModels] = useState<HondaModelOption[]>([]);
  const [configurations, setConfigurations] = useState<HondaCatalogConfiguration[]>([]);
  const [catalogNote, setCatalogNote] = useState('Loading exact Honda catalog configurations…');
  const [modelsLoading, setModelsLoading] = useState(false);
  const [configsLoading, setConfigsLoading] = useState(false);
  const [vinLoading, setVinLoading] = useState(false);
  const [error, setError] = useState('');
  const [detailsOpen, setDetailsOpen] = useState(value.source === 'nhtsa-vin');

  const fallbackYears = useMemo(() => hondaModelYears(), []);
  const trimLabel = identityTrimLabel(value);
  const engineLabel = identityEngineLabel(value);
  const selectedConfiguration = configurations.find((option) => option.key === configurationKey);

  useEffect(() => {
    let cancelled = false;
    Promise.all([catalogYears(), catalogStats()])
      .then(([catalogYearValues, stats]) => {
        if (cancelled) return;
        setYears(catalogYearValues);
        setCatalogNote(`${stats.recordCount.toLocaleString()} exact catalog configurations · ${stats.modelCount} Honda model lines · zero LLM tokens`);
        if (!catalogYearValues.includes(year) && catalogYearValues.length) setYear(catalogYearValues[0]);
      })
      .catch(() => {
        if (cancelled) return;
        setYears(fallbackYears);
        setCatalogNote('The static exact-configuration catalog is unavailable. Model-only fallback is shown; PartGraph will not pretend a trim is verified.');
      });
    return () => { cancelled = true; };
  }, [fallbackYears, year]);

  useEffect(() => {
    let cancelled = false;
    setModelsLoading(true);
    setError('');
    catalogModels(year)
      .catch(async () => (await fetchHondaModels(year)).models)
      .then((options) => {
        if (cancelled) return;
        setModels(options);
        const exact = options.find((option) => option.name.toLowerCase() === model.toLowerCase());
        if (!exact) {
          setModel(options[0]?.name ?? '');
          setConfigurationKey('');
        } else if (model !== exact.name) {
          setModel(exact.name);
        }
      })
      .finally(() => { if (!cancelled) setModelsLoading(false); });
    return () => { cancelled = true; };
  }, [year]);

  useEffect(() => {
    let cancelled = false;
    if (!model) {
      setConfigurations([]);
      return () => { cancelled = true; };
    }
    setConfigsLoading(true);
    catalogConfigurations(year, model)
      .then((options) => {
        if (cancelled) return;
        setConfigurations(options);
        if (!options.some((option) => option.key === configurationKey)) setConfigurationKey(options[0]?.key ?? '');
      })
      .catch(() => {
        if (!cancelled) setConfigurations([]);
      })
      .finally(() => { if (!cancelled) setConfigsLoading(false); });
    return () => { cancelled = true; };
  }, [year, model]);

  const useCatalogVehicle = () => {
    setError('');
    const selected = configurations.find((option) => option.key === configurationKey);
    if (!model) {
      setError('Choose the Honda model.');
      return;
    }
    if (!selected) {
      setError('Choose an exact body/trim and emission/transmission configuration. PartGraph will not guess one.');
      return;
    }
    const identity: CatalogHondaVehicleIdentity = {
      ...manualHondaIdentity(year, model, selected.bodyTrim),
      catalogVerified: true,
      catalogKey: selected.key,
      catalogSourceUrl: selected.sourceUrl,
      bodyTrim: selected.bodyTrim,
      emissionTransmission: selected.emissionTransmission,
      series: selected.emissionTransmission,
    };
    onChange(identity);
    setDetailsOpen(true);
  };

  const decodeVin = async () => {
    const normalized = normalizeVin(vin);
    setVin(normalized);
    setError('');
    if (!isCompleteVin(normalized)) {
      setError('Enter all 17 VIN characters. VINs do not use I, O or Q.');
      return;
    }
    setVinLoading(true);
    try {
      const decoded = await decodeHondaVin(normalized);
      onChange(decoded);
      setYear(decoded.year);
      setModel(decoded.model);
      setConfigurationKey('');
      setDetailsOpen(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'VIN lookup failed.');
    } finally {
      setVinLoading(false);
    }
  };

  const useDemo = () => {
    setError('');
    setMode('catalog');
    setVin('');
    setYear(demoHondaIdentity.year);
    setModel(demoHondaIdentity.model);
    setConfigurationKey('');
    onChange(demoHondaIdentity);
  };

  return (
    <section className="pg-vehicle-finder" aria-labelledby="pg-vehicle-title">
      <div className="pg-vehicle-heading">
        <div>
          <span className="pg-eyebrow">STEP 1 · IDENTIFY THE VEHICLE</span>
          <h2 id="pg-vehicle-title">Which Honda are we repairing?</h2>
          <p>Choose the exact catalog configuration, or use a VIN. The catalog path keeps body/trim and emission/transmission separate so parts are never borrowed from a nearby trim.</p>
        </div>
        <div className="pg-id-source">
          {value.source === 'nhtsa-vin' || value.catalogVerified === true ? <ShieldCheck size={16} /> : <CarFront size={16} />}
          <span><small>Current vehicle</small><strong>{value.year} Honda {value.model}</strong></span>
        </div>
      </div>

      <div className="pg-finder-mode" role="tablist" aria-label="Vehicle identification method">
        <button type="button" className={mode === 'catalog' ? 'active' : ''} onClick={() => { setMode('catalog'); setError(''); }}>
          <Database size={15} /> Exact catalog configuration
        </button>
        <button type="button" className={mode === 'vin' ? 'active' : ''} onClick={() => { setMode('vin'); setError(''); }}>
          <ScanLine size={15} /> VIN — optional cross-check
        </button>
      </div>

      {mode === 'catalog' ? (
        <div className="pg-manual-grid">
          <label className="pg-field">
            <span>Year</span>
            <select value={year} onChange={(event) => { setYear(Number(event.target.value)); setModel(''); setConfigurationKey(''); }}>
              {(years.length ? years : fallbackYears).map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
          </label>

          <label className="pg-field pg-field--model">
            <span>Model {modelsLoading ? <LoaderCircle className="pg-spin" size={12} /> : null}</span>
            <select value={model} onChange={(event) => { setModel(event.target.value); setConfigurationKey(''); }} disabled={modelsLoading || !models.length}>
              {!models.length ? <option value="">No catalog models</option> : null}
              {models.map((option) => <option key={`${option.id}-${option.name}`} value={option.name}>{option.name}</option>)}
            </select>
          </label>

          <label className="pg-field pg-field--trim">
            <span>Exact configuration {configsLoading ? <LoaderCircle className="pg-spin" size={12} /> : null}</span>
            <select value={configurationKey} onChange={(event) => setConfigurationKey(event.target.value)} disabled={configsLoading || !configurations.length}>
              {!configurations.length ? <option value="">No verified configuration loaded</option> : null}
              {configurations.map((option) => <option key={option.key} value={option.key}>{option.configurationLabel}</option>)}
            </select>
          </label>

          <button className="pg-manual-submit" type="button" onClick={useCatalogVehicle} disabled={!selectedConfiguration}>Use this Honda</button>
          <p className="pg-model-note">{catalogNote}</p>
          {selectedConfiguration ? (
            <p className="pg-model-note">
              Source identity: {selectedConfiguration.configurationLabel} ·{' '}
              <a href={selectedConfiguration.sourceUrl} target="_blank" rel="noreferrer">verify catalog page <ExternalLink size={11} /></a>
            </p>
          ) : null}
        </div>
      ) : (
        <div className="pg-vin-row">
          <label className="pg-field pg-field--vin">
            <span>17-character VIN</span>
            <input value={vin} onChange={(event) => setVin(normalizeVin(event.target.value))} onKeyDown={(event) => { if (event.key === 'Enter') void decodeVin(); }} inputMode="text" autoCapitalize="characters" autoComplete="off" spellCheck={false} placeholder="2HGFA…" maxLength={17} aria-label="Honda VIN" />
            <small>{vin.length}/17</small>
          </label>
          <button className="pg-vin-submit" type="button" onClick={() => void decodeVin()} disabled={vinLoading}>
            {vinLoading ? <LoaderCircle className="pg-spin" size={16} /> : <ScanLine size={16} />}
            {vinLoading ? 'Decoding…' : 'Decode VIN'}
          </button>
          <div className="pg-vin-source-note">
            <Database size={14} />
            <span>NHTSA vPIC public decoder · no API key · no LLM tokens</span>
            <a href="https://vpic.nhtsa.dot.gov/" target="_blank" rel="noreferrer" aria-label="Open NHTSA vPIC">Source <ExternalLink size={11} /></a>
          </div>
        </div>
      )}

      {error ? <div className="pg-id-error" role="alert"><AlertTriangle size={15} /> {error}</div> : null}

      <div className={`pg-identity-card ${value.source === 'nhtsa-vin' || value.catalogVerified === true ? 'verified' : ''}`}>
        <div className="pg-identity-primary">
          <span className="pg-id-badge">
            {value.source === 'nhtsa-vin' ? <><ShieldCheck size={13} /> VIN decoded</> : value.catalogVerified ? <><ShieldCheck size={13} /> Catalog configuration</> : <><CarFront size={13} /> Demo/manual identity</>}
          </span>
          <strong>{value.year} Honda {value.model}</strong>
          <span>{value.bodyTrim || trimLabel}</span>
          <small>{value.emissionTransmission || engineLabel}</small>
        </div>
        <button type="button" className="pg-id-details-toggle" onClick={() => setDetailsOpen((open) => !open)}>{detailsOpen ? 'Hide identifiers' : 'Show identifiers'}</button>

        {detailsOpen ? (
          <div className="pg-id-facts">
            <Identifier label="Body & trim" value={value.bodyTrim || value.trim} />
            <Identifier label="Emission & transmission" value={value.emissionTransmission} />
            <Identifier label="Trim 2" value={value.trim2} />
            <Identifier label="Series" value={value.series} />
            <Identifier label="Series 2" value={value.series2} />
            <Identifier label="Body" value={value.bodyClass} />
            <Identifier label="Vehicle type" value={value.vehicleType} />
            <Identifier label="Doors" value={value.doors} />
            <Identifier label="Drive" value={value.driveType} />
            <Identifier label="Engine" value={value.engineModel} />
            <Identifier label="Displacement" value={value.displacementL ? `${value.displacementL} L` : undefined} />
            <Identifier label="Cylinders" value={value.engineCylinders} />
            <Identifier label="Primary fuel" value={value.fuelTypePrimary} />
            <Identifier label="Secondary fuel" value={value.fuelTypeSecondary} />
            <Identifier label="Electrification" value={value.electrificationLevel} />
            <Identifier label="Transmission" value={value.transmissionStyle} />
            <Identifier label="Transmission speeds" value={value.transmissionSpeeds} />
            <Identifier label="Plant" value={[value.plantCity, value.plantState, value.plantCountry].filter(Boolean).join(', ') || undefined} />
            <Identifier label="Destination market" value={value.destinationMarket} />
          </div>
        ) : null}
        {value.catalogSourceUrl ? <a className="pg-id-details-toggle" href={value.catalogSourceUrl} target="_blank" rel="noreferrer">Open exact catalog source <ExternalLink size={11} /></a> : null}
      </div>

      <div className="pg-id-footnote">
        <CheckCircle2 size={14} />
        <span>PartGraph uses the catalog's exact Body & Trim plus Emission & Transmission identity. A model/year alone is never treated as exact fitment.</span>
        <button type="button" onClick={useDemo}>Reset to demo Honda</button>
      </div>
    </section>
  );
}
