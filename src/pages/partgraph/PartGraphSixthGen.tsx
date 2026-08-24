import {useEffect, useMemo, useState} from 'react';
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  ExternalLink,
  Image as ImageIcon,
  PackageCheck,
  RotateCcw,
  ShieldCheck,
  ShoppingCart,
  Smartphone,
  Wrench,
} from 'lucide-react';
import {
  CIVIC_SIXTH_GEN_YEARS,
  resolveCivicSixthGenCooling,
  sixthGenDefaultState,
  type SixthGenPart,
  type SixthGenPartState,
} from '../../data/hondaCivic6thGen';
import {
  fetchHondaManualConfigurations,
  type HondaManualConfiguration,
} from '../../lib/hondaManualConfigurationService';
import {
  fetchHondaModels,
  hondaModelYears,
  type HondaModelOption,
} from '../../lib/hondaVehicleService';
import {hondaGenerationNote} from '../../lib/hondaVehicleLabels';
import {PartGraphSelect, type PartGraphSelectOption} from './PartGraphSelect';
import '../../styles/partgraph-sixth-gen.css';

const APP_URL = 'https://vivek-k24.github.io/forgebridge-demo/#/';
const QR_URL = `https://api.qrserver.com/v1/create-qr-code/?size=120x120&margin=4&data=${encodeURIComponent(APP_URL)}`;
const STORAGE_PREFIX = 'partgraph.honda.front-cooling.';

type RepairBlock = 'cooling' | 'air-conditioning' | 'brakes' | 'suspension';

const blockOptions: PartGraphSelectOption[] = [
  {value: 'cooling', label: 'Cooling', secondary: 'Radiator, fans, hoses and mounts'},
  {value: 'air-conditioning', label: 'Air conditioning', secondary: 'More repair maps coming later'},
  {value: 'brakes', label: 'Brakes', secondary: 'More repair maps coming later'},
  {value: 'suspension', label: 'Suspension', secondary: 'More repair maps coming later'},
];

const stateLabels: Record<SixthGenPartState, string> = {
  need: 'Need',
  have: 'Have',
  inspect: 'Inspect',
  'not-sure': 'Not sure',
};

function productSearchLinks(part: SixthGenPart) {
  const q = encodeURIComponent(`"${part.oemNumber}" Honda`);
  return [
    {
      name: 'HondaPartsNow',
      url: `https://www.google.com/search?q=${encodeURIComponent(`site:hondapartsnow.com "${part.oemNumber}"`)}`,
    },
    {
      name: 'Honda Factory Parts',
      url: `https://www.google.com/search?q=${encodeURIComponent(`site:hondafactoryparts.com "${part.oemNumber}"`)}`,
    },
    {
      name: 'Honda Parts Online',
      url: `https://www.google.com/search?q=${encodeURIComponent(`site:hondapartsonline.net "${part.oemNumber}"`)}`,
    },
    {
      name: 'AutoPartsPrime',
      url: `https://www.google.com/search?q=${encodeURIComponent(`site:autopartsprime.com "${part.oemNumber}"`)}`,
    },
    {name: 'eBay', url: `https://www.ebay.com/sch/i.html?_nkw=${q}`},
  ];
}

function PartGlyph({part}: {part: SixthGenPart}) {
  const glyph =
    part.group === 'fan'
      ? '✣'
      : part.group === 'hose'
        ? '∿'
        : part.group === 'hardware'
          ? '⌁'
          : part.group === 'mount'
            ? '⌐'
            : part.group === 'reservoir'
              ? '▱'
              : '▦';

  return (
    <span className={`pg6-glyph pg6-glyph--${part.group}`} aria-hidden="true">
      {glyph}
    </span>
  );
}

function StateButtons({
  value,
  onChange,
}: {
  value: SixthGenPartState;
  onChange: (state: SixthGenPartState) => void;
}) {
  const values: SixthGenPartState[] = ['need', 'have', 'inspect', 'not-sure'];
  return (
    <div className="pg6-state-buttons" role="group" aria-label="Part state">
      {values.map((item) => (
        <button
          key={item}
          type="button"
          className={value === item ? 'active' : ''}
          onClick={() => onChange(item)}
        >
          {stateLabels[item]}
        </button>
      ))}
    </div>
  );
}

export function PartGraphSixthGen() {
  const [year, setYear] = useState<number>(2000);
  const [model, setModel] = useState('Civic');
  const [models, setModels] = useState<HondaModelOption[]>([]);
  const [modelLoading, setModelLoading] = useState(false);
  const [configurations, setConfigurations] = useState<HondaManualConfiguration[]>([]);
  const [configurationKey, setConfigurationKey] = useState('');
  const [configurationLoading, setConfigurationLoading] = useState(false);
  const [block, setBlock] = useState<RepairBlock>('cooling');
  const [targetPartId, setTargetPartId] = useState('radiator');
  const [states, setStates] = useState<Record<string, SixthGenPartState>>({});
  const [photoUrl, setPhotoUrl] = useState('');
  const [photoName, setPhotoName] = useState('');
  const [savedAt, setSavedAt] = useState('');

  useEffect(() => {
    let cancelled = false;
    setModelLoading(true);
    fetchHondaModels(year)
      .then((result) => {
        if (cancelled) return;
        setModels(result.models);
        setModel((current) =>
          result.models.some((item) => item.name === current)
            ? current
            : (result.models[0]?.name ?? ''),
        );
      })
      .finally(() => {
        if (!cancelled) setModelLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [year]);

  useEffect(() => {
    let cancelled = false;
    if (!model) {
      setConfigurations([]);
      setConfigurationKey('');
      return undefined;
    }

    setConfigurationLoading(true);
    fetchHondaManualConfigurations(year, model)
      .then((result) => {
        if (cancelled) return;
        setConfigurations(result.options);
        setConfigurationKey((current) =>
          result.options.some((item) => item.value === current)
            ? current
            : (result.options[0]?.value ?? ''),
        );
      })
      .finally(() => {
        if (!cancelled) setConfigurationLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [year, model]);

  useEffect(
    () => () => {
      if (photoUrl) URL.revokeObjectURL(photoUrl);
    },
    [photoUrl],
  );

  const selectedConfiguration =
    configurations.find((item) => item.value === configurationKey) ?? null;
  const sixthGenCivic =
    model === 'Civic' &&
    CIVIC_SIXTH_GEN_YEARS.includes(year as (typeof CIVIC_SIXTH_GEN_YEARS)[number]);

  const resolution = useMemo(() => {
    if (!selectedConfiguration || !sixthGenCivic) return null;
    return resolveCivicSixthGenCooling({
      year,
      bodyTrim: selectedConfiguration.bodyTrim,
      emissionTransmission: selectedConfiguration.emissionTransmission,
      sourceUrl: selectedConfiguration.sourceUrl,
    });
  }, [year, selectedConfiguration, sixthGenCivic]);

  const published = block === 'cooling' && resolution?.status === 'verified';
  const parts = published && resolution ? resolution.parts : [];
  const targetOptions = parts
    .filter((part) => part.group !== 'hardware')
    .map((part) => ({
      value: part.id,
      label: part.name,
      secondary: `OEM ${part.oemNumber}`,
    }));

  useEffect(() => {
    if (!published || !resolution) return;
    const next = Object.fromEntries(
      resolution.parts.map((part) => [part.id, sixthGenDefaultState(part)]),
    );
    try {
      const raw = localStorage.getItem(`${STORAGE_PREFIX}${configurationKey}`);
      setStates(
        raw
          ? {...next, ...(JSON.parse(raw) as Record<string, SixthGenPartState>)}
          : next,
      );
    } catch {
      setStates(next);
    }
    setTargetPartId((current) =>
      resolution.parts.some((part) => part.id === current) ? current : 'radiator',
    );
    setSavedAt('');
  }, [published, resolution, configurationKey]);

  const needParts = parts.filter((part) => states[part.id] === 'need');
  const unresolved = parts.filter((part) => states[part.id] === 'not-sure').length;
  const generationNote = hondaGenerationNote(year, model);
  const yearOptions = hondaModelYears().map((item) => ({
    value: String(item),
    label: String(item),
  }));
  const modelOptions = models.map((item) => ({value: item.name, label: item.name}));
  const configurationOptions = configurations.map((item) => ({
    value: item.value,
    label: item.label,
    secondary: item.secondary,
  }));
  const has2009HybridMap =
    year === 2009 && model === 'Civic' && /hybrid/i.test(selectedConfiguration?.label ?? '');

  const changeState = (partId: string, state: SixthGenPartState) => {
    setStates((current) => ({...current, [partId]: state}));
  };

  const save = () => {
    if (!published) return;
    localStorage.setItem(`${STORAGE_PREFIX}${configurationKey}`, JSON.stringify(states));
    setSavedAt(new Date().toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'}));
  };

  const reset = () => {
    if (!resolution || resolution.status !== 'verified') return;
    const next = Object.fromEntries(
      resolution.parts.map((part) => [part.id, sixthGenDefaultState(part)]),
    );
    setStates(next);
    localStorage.removeItem(`${STORAGE_PREFIX}${configurationKey}`);
    setSavedAt('');
  };

  const takePhoto = (file?: File) => {
    if (!file) return;
    if (photoUrl) URL.revokeObjectURL(photoUrl);
    setPhotoUrl(URL.createObjectURL(file));
    setPhotoName(file.name);
  };

  return (
    <main className="pg6-shell">
      <header className="pg6-header">
        <a className="pg6-brand" href="#/">
          <span><Wrench size={18} /></span>
          <strong>PARTGRAPH</strong>
          <small>Complete repair parts</small>
        </a>
        <nav>
          <button type="button" onClick={save} disabled={!published}>
            {savedAt ? `Saved ${savedAt}` : 'Save repair'}
          </button>
        </nav>
      </header>

      <section className="pg6-hero">
        <div>
          <span className="pg6-kicker">HONDA PARTS & REPAIR</span>
          <h1>Find every part your repair needs.</h1>
          <p>
            Choose your Honda and the part you are replacing. We will walk through what
            connects to it, what to inspect, and the exact part identities we can verify.
          </p>
        </div>
        <aside className="pg6-qr">
          <img src={QR_URL} alt="QR code to open PartGraph on a phone" />
          <span>
            <Smartphone size={16} />
            <strong>Open on phone</strong>
            <small>Take photos beside the car.</small>
          </span>
        </aside>
      </section>

      <section className="pg6-flow">
        <div className="pg6-flow-heading">
          <span>1</span>
          <div>
            <strong>Your vehicle</strong>
            <small>U.S. / Canada catalog scope</small>
          </div>
        </div>

        <div className="pg6-select-grid">
          <PartGraphSelect
            label="Make"
            value="Honda"
            options={[{value: 'Honda', label: 'Honda'}]}
            onChange={() => undefined}
          />
          <PartGraphSelect
            label="Year"
            value={String(year)}
            options={yearOptions}
            onChange={(value) => setYear(Number(value))}
            helperText={generationNote}
          />
          <PartGraphSelect
            label={modelLoading ? 'Model · loading' : 'Model'}
            value={model}
            options={modelOptions}
            onChange={setModel}
            placeholder="Choose model"
          />
          <PartGraphSelect
            label={configurationLoading ? 'Trim · loading' : 'Trim'}
            value={configurationKey}
            options={configurationOptions}
            onChange={setConfigurationKey}
            placeholder="Choose trim"
          />
        </div>

        {selectedConfiguration ? (
          <p className="pg6-source-line">
            <CheckCircle2 size={13} />
            Selected: <strong>{year} Honda {model} · {selectedConfiguration.label}</strong>
            {selectedConfiguration.secondary ? ` · ${selectedConfiguration.secondary}` : ''}
            <a href={selectedConfiguration.sourceUrl} target="_blank" rel="noreferrer">
              View catalog <ExternalLink size={11} />
            </a>
          </p>
        ) : null}

        <div className="pg6-flow-heading">
          <span>2</span>
          <div>
            <strong>What are you repairing?</strong>
            <small>System → area → main part</small>
          </div>
        </div>

        <div className="pg6-select-grid pg6-select-grid--repair">
          <PartGraphSelect
            label="System"
            value={block}
            options={blockOptions}
            onChange={(value) => setBlock(value as RepairBlock)}
          />
          <PartGraphSelect
            label="Area"
            value={block === 'cooling' ? 'front-cooling' : ''}
            options={
              block === 'cooling'
                ? [{value: 'front-cooling', label: 'Front cooling / radiator'}]
                : [{value: '', label: 'Not available yet', disabled: true}]
            }
            onChange={() => undefined}
          />
          <PartGraphSelect
            label="Main part"
            value={published ? targetPartId : ''}
            options={
              published
                ? targetOptions
                : [{value: '', label: 'Choose a supported repair', disabled: true}]
            }
            onChange={setTargetPartId}
          />
        </div>

        {published && resolution ? (
          <div className="pg6-ready">
            <ShieldCheck size={16} />
            <span>
              <strong>Exact parts map ready</strong>
              {year} Honda Civic · {selectedConfiguration?.label} · radiator{' '}
              <code>{resolution.radiatorNumber}</code>
            </span>
          </div>
        ) : selectedConfiguration ? (
          <div className="pg6-unavailable">
            <AlertTriangle size={22} />
            <div>
              <span>NOT VERIFIED YET</span>
              <h2>We do not have a complete repair map for this exact vehicle yet.</h2>
              <p>
                PartGraph will not borrow parts from another trim, transmission or market.
                You can still open the source catalog, or choose a vehicle with a verified map.
              </p>
              <div className="pg6-unavailable-actions">
                <a href={selectedConfiguration.sourceUrl} target="_blank" rel="noreferrer">
                  <ExternalLink size={14} /> View vehicle catalog
                </a>
                {has2009HybridMap ? (
                  <a href="#/8th-gen">Open the 2009 Civic Hybrid repair map</a>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}
      </section>

      {published && resolution ? (
        <>
          <section className="pg6-camera">
            <div className="pg6-camera-copy">
              <Camera size={24} />
              <div>
                <span>PHOTO HELP</span>
                <h2>If you’re not sure what the parts are called, let us take a look.</h2>
                <p>
                  Take or choose a photo on your phone. For now the image stays on your device
                  and is used only as a local preview.
                </p>
              </div>
            </div>
            {photoUrl ? (
              <div className="pg6-photo">
                <img src={photoUrl} alt="Selected car part" />
                <span>
                  <strong>{photoName}</strong>
                  <small>Local preview only</small>
                </span>
                <label>
                  Retake
                  <input
                    type="file"
                    accept="image/*"
                    capture="environment"
                    onChange={(event) => takePhoto(event.target.files?.[0])}
                  />
                </label>
              </div>
            ) : (
              <label className="pg6-camera-button">
                <Camera size={17} /> Take or choose part photo
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  onChange={(event) => takePhoto(event.target.files?.[0])}
                />
              </label>
            )}
          </section>

          <section className="pg6-assembly">
            <div className="pg6-section-title">
              <div>
                <span>ASSEMBLY CHECK</span>
                <h2>What do you still need?</h2>
                <p>
                  {parts.length} verified component records are available for this cooling
                  assembly. Open the diagram whenever a name is not enough.
                </p>
              </div>
              <div className="pg6-count">
                <strong>{unresolved}</strong>
                <small>not sure</small>
              </div>
            </div>

            <div className="pg6-parts">
              {parts.map((part) => {
                const state = states[part.id] ?? sixthGenDefaultState(part);
                return (
                  <article
                    className={`pg6-part pg6-part--${state} ${part.id === targetPartId ? 'target' : ''}`}
                    key={part.id}
                  >
                    <a
                      className="pg6-part-visual"
                      href={part.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                      title="Open parts diagram"
                    >
                      <PartGlyph part={part} />
                      <span><ImageIcon size={11} /> Diagram</span>
                    </a>
                    <div className="pg6-part-copy">
                      <div className="pg6-meta">
                        {part.id === targetPartId ? <b>Main part</b> : null}
                        <em>Verified</em>
                        <code>{part.oemNumber}</code>
                        {part.quantity > 1 ? <i>×{part.quantity}</i> : null}
                      </div>
                      <h3>{part.name}</h3>
                      <p>{part.note}</p>
                      {part.alternateNumbers?.length ? (
                        <small className="pg6-alt">
                          Alternate / supplier number: {part.alternateNumbers.join(', ')}
                        </small>
                      ) : null}
                      {part.replacedNumbers?.length ? (
                        <small className="pg6-alt">
                          Replaces / older number: {part.replacedNumbers.join(', ')}
                        </small>
                      ) : null}
                    </div>
                    <StateButtons value={state} onChange={(next) => changeState(part.id, next)} />
                  </article>
                );
              })}
            </div>

            <div className="pg6-sticky">
              <span>
                <strong>{needParts.length} to find</strong>
                <small>Exact part identities only</small>
              </span>
              <a href="#pg6-buy"><ShoppingCart size={15} /> Purchase links</a>
              <button type="button" onClick={reset}><RotateCcw size={14} /> Reset</button>
            </div>
          </section>

          <section className="pg6-buy" id="pg6-buy">
            <div className="pg6-section-title compact">
              <div>
                <span>PARTS TO BUY</span>
                <h2>
                  {needParts.length
                    ? `${needParts.length} selected item${needParts.length === 1 ? '' : 's'}`
                    : 'Mark a part Need to shop it'}
                </h2>
                <p>
                  Each search starts with the verified OEM number. Seller fitment badges do
                  not override the PartGraph identity.
                </p>
              </div>
              <PackageCheck size={28} />
            </div>

            <div className="pg6-buy-list">
              {needParts.map((part) => (
                <article key={part.id} className="pg6-buy-card">
                  <PartGlyph part={part} />
                  <div>
                    <strong>{part.name}{part.quantity > 1 ? ` ×${part.quantity}` : ''}</strong>
                    <code>{part.oemNumber}</code>
                  </div>
                  <div className="pg6-links">
                    {productSearchLinks(part).map((link) => (
                      <a key={link.name} href={link.url} target="_blank" rel="noreferrer">
                        {link.name}<ExternalLink size={11} />
                      </a>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="pg6-provenance">
            <ShieldCheck size={18} />
            <div>
              <strong>Why you can trust this list</strong>
              <p>
                The vehicle configuration and part identities link back to their catalog
                sources. We do not invent torque values, fluid quantities or repair procedures
                when those facts have not been verified.
              </p>
              <div>
                {resolution.radiatorSourceUrl ? (
                  <a href={resolution.radiatorSourceUrl} target="_blank" rel="noreferrer">
                    Radiator diagram <ExternalLink size={11} />
                  </a>
                ) : null}
                {resolution.hoseSourceUrl ? (
                  <a href={resolution.hoseSourceUrl} target="_blank" rel="noreferrer">
                    Hose / mount diagram <ExternalLink size={11} />
                  </a>
                ) : null}
              </div>
            </div>
          </section>
        </>
      ) : null}

      <footer className="pg6-footer">
        PartGraph shows sourced repair relationships. If we cannot verify a fitment, we do not guess.
      </footer>
    </main>
  );
}
