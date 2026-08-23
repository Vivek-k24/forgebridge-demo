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
  decodeHondaVin,
  demoHondaIdentity,
  fetchHondaModels,
  hondaModelYears,
  hondaTrimSuggestions,
  identityEngineLabel,
  identityTrimLabel,
  isCompleteVin,
  manualHondaIdentity,
  normalizeVin,
  type HondaModelOption,
  type HondaVehicleIdentity,
} from '../../lib/hondaVehicleService';

type FinderMode = 'vin' | 'manual';

interface HondaVehicleSelectorProps {
  value: HondaVehicleIdentity;
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
  const [mode, setMode] = useState<FinderMode>(value.source === 'nhtsa-vin' ? 'vin' : 'manual');
  const [vin, setVin] = useState(value.vin ?? '');
  const [year, setYear] = useState(value.year);
  const [model, setModel] = useState(value.model);
  const [trim, setTrim] = useState(value.trim ?? '');
  const [models, setModels] = useState<HondaModelOption[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelListNote, setModelListNote] = useState('');
  const [vinLoading, setVinLoading] = useState(false);
  const [error, setError] = useState('');
  const [detailsOpen, setDetailsOpen] = useState(value.source === 'nhtsa-vin');

  const years = useMemo(() => hondaModelYears(), []);
  const trimLabel = identityTrimLabel(value);
  const engineLabel = identityEngineLabel(value);

  useEffect(() => {
    let cancelled = false;
    setModelsLoading(true);
    setModelListNote('');

    fetchHondaModels(year)
      .then((result) => {
        if (cancelled) return;
        setModels(result.models);
        if (!result.yearScoped) {
          setModelListNote(year < 1996
            ? 'NHTSA does not expose year-filtered model discovery before 1996. VIN decoding is the safer path for older Hondas.'
            : 'Live model discovery was unavailable, so a local Honda automobile fallback list is shown.');
        } else if (result.fromCache) {
          setModelListNote('Honda model list loaded from a 30-day local cache.');
        }
      })
      .catch(() => {
        if (!cancelled) setModelListNote('Honda model discovery is temporarily unavailable. Type the model manually or use the VIN path.');
      })
      .finally(() => {
        if (!cancelled) setModelsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [year]);

  useEffect(() => {
    if (!models.length || !model) return;
    const exact = models.find((option) => option.name.toLowerCase() === model.toLowerCase());
    if (exact) setModel(exact.name);
  }, [models, model]);

  const useManualVehicle = () => {
    setError('');
    if (!model.trim()) {
      setError('Choose or type the Honda model.');
      return;
    }
    onChange(manualHondaIdentity(year, model, trim));
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
      setTrim(decoded.trim || decoded.trim2 || decoded.series || decoded.series2 || '');
      setDetailsOpen(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'VIN lookup failed.');
    } finally {
      setVinLoading(false);
    }
  };

  const useDemo = () => {
    setError('');
    setMode('manual');
    setVin('');
    setYear(demoHondaIdentity.year);
    setModel(demoHondaIdentity.model);
    setTrim(demoHondaIdentity.trim ?? '');
    onChange(demoHondaIdentity);
  };

  return (
    <section className="pg-vehicle-finder" aria-labelledby="pg-vehicle-title">
      <div className="pg-vehicle-heading">
        <div>
          <span className="pg-eyebrow">STEP 1 · IDENTIFY THE VEHICLE</span>
          <h2 id="pg-vehicle-title">Which Honda are we repairing?</h2>
          <p>Use a VIN for the strongest identification, or choose the vehicle manually. This step never calls a language model.</p>
        </div>
        <div className="pg-id-source">
          {value.source === 'nhtsa-vin' ? <ShieldCheck size={16} /> : <CarFront size={16} />}
          <span><small>Current vehicle</small><strong>{value.year} Honda {value.model}</strong></span>
        </div>
      </div>

      <div className="pg-finder-mode" role="tablist" aria-label="Vehicle identification method">
        <button type="button" className={mode === 'vin' ? 'active' : ''} onClick={() => { setMode('vin'); setError(''); }}>
          <ScanLine size={15} /> VIN — fastest / most precise
        </button>
        <button type="button" className={mode === 'manual' ? 'active' : ''} onClick={() => { setMode('manual'); setError(''); }}>
          <CarFront size={15} /> Choose manually
        </button>
      </div>

      {mode === 'vin' ? (
        <div className="pg-vin-row">
          <label className="pg-field pg-field--vin">
            <span>17-character VIN</span>
            <input
              value={vin}
              onChange={(event) => setVin(normalizeVin(event.target.value))}
              onKeyDown={(event) => { if (event.key === 'Enter') void decodeVin(); }}
              inputMode="text"
              autoCapitalize="characters"
              autoComplete="off"
              spellCheck={false}
              placeholder="2HGFA..."
              maxLength={17}
              aria-label="Honda VIN"
            />
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
      ) : (
        <div className="pg-manual-grid">
          <label className="pg-field">
            <span>Year</span>
            <select value={year} onChange={(event) => { setYear(Number(event.target.value)); setModel(''); }}>
              {years.map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
          </label>

          <label className="pg-field pg-field--model">
            <span>Model {modelsLoading ? <LoaderCircle className="pg-spin" size={12} /> : null}</span>
            <input
              list="pg-honda-models"
              value={model}
              onChange={(event) => setModel(event.target.value)}
              placeholder="Civic, Accord, CR-V…"
              autoComplete="off"
            />
            <datalist id="pg-honda-models">
              {models.map((option) => <option key={`${option.id}-${option.name}`} value={option.name} />)}
            </datalist>
          </label>

          <label className="pg-field pg-field--trim">
            <span>Trim / series</span>
            <input
              list="pg-honda-trims"
              value={trim}
              onChange={(event) => setTrim(event.target.value)}
              placeholder="Hybrid, EX-L, Touring…"
              autoComplete="off"
            />
            <datalist id="pg-honda-trims">
              {hondaTrimSuggestions.map((option) => <option key={option} value={option} />)}
            </datalist>
          </label>

          <button className="pg-manual-submit" type="button" onClick={useManualVehicle}>Use this Honda</button>
          {modelListNote ? <p className="pg-model-note">{modelListNote}</p> : null}
        </div>
      )}

      {error ? <div className="pg-id-error" role="alert"><AlertTriangle size={15} /> {error}</div> : null}

      <div className={`pg-identity-card ${value.source === 'nhtsa-vin' ? 'verified' : ''}`}>
        <div className="pg-identity-primary">
          <span className="pg-id-badge">{value.source === 'nhtsa-vin' ? <><ShieldCheck size={13} /> VIN decoded</> : <><CarFront size={13} /> Manual identity</>}</span>
          <strong>{value.year} Honda {value.model}</strong>
          <span>{trimLabel}</span>
          <small>{engineLabel}</small>
        </div>
        <button type="button" className="pg-id-details-toggle" onClick={() => setDetailsOpen((open) => !open)}>
          {detailsOpen ? 'Hide identifiers' : 'Show identifiers'}
        </button>

        {detailsOpen ? (
          <div className="pg-id-facts">
            <Identifier label="Trim" value={value.trim} />
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
      </div>

      <div className="pg-id-footnote">
        <CheckCircle2 size={14} />
        <span>VIN decoding can return trim, series, body, engine, transmission, fuel and plant identifiers when Honda reported them to NHTSA. A blank field means “not reported,” not “feature absent.”</span>
        <button type="button" onClick={useDemo}>Reset to verified demo Honda</button>
      </div>
    </section>
  );
}
