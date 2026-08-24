import {useEffect, useMemo, useState} from 'react';
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  Clipboard,
  ExternalLink,
  Image as ImageIcon,
  PackageCheck,
  RotateCcw,
  Search,
  ShieldCheck,
  ShoppingCart,
  Smartphone,
  Wrench,
} from 'lucide-react';
import {
  CIVIC_SIXTH_GEN_LABEL,
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
import {PartGraphSelect, type PartGraphSelectOption} from './PartGraphSelect';
import '../../styles/partgraph-sixth-gen.css';

const APP_URL = 'https://vivek-k24.github.io/forgebridge-demo/#/';
const QR_URL = `https://api.qrserver.com/v1/create-qr-code/?size=120x120&margin=4&data=${encodeURIComponent(APP_URL)}`;
const STORAGE_PREFIX = 'partgraph.civic6.front-cooling.';

type RepairBlock = 'cooling' | 'air-conditioning' | 'brakes' | 'suspension';

const blockOptions: PartGraphSelectOption[] = [
  {value: 'cooling', label: 'Cooling', secondary: 'Front radiator assembly published'},
  {value: 'air-conditioning', label: 'Air conditioning', secondary: 'Data not published for 6th gen yet'},
  {value: 'brakes', label: 'Brakes', secondary: 'Data not published for 6th gen yet'},
  {value: 'suspension', label: 'Suspension', secondary: 'Data not published for 6th gen yet'},
];

const stateLabels: Record<SixthGenPartState, string> = {
  need: 'Need',
  have: 'Have',
  inspect: 'Inspect',
  'not-sure': 'Not sure',
};

function productSearchLinks(part: SixthGenPart) {
  const q = encodeURIComponent(`"${part.oemNumber}" Honda Civic`);
  return [
    {name: 'HondaPartsNow', url: `https://www.google.com/search?q=${encodeURIComponent(`site:hondapartsnow.com "${part.oemNumber}"`)}`},
    {name: 'Honda Factory Parts', url: `https://www.google.com/search?q=${encodeURIComponent(`site:hondafactoryparts.com "${part.oemNumber}"`)}`},
    {name: 'Honda Parts Online', url: `https://www.google.com/search?q=${encodeURIComponent(`site:hondapartsonline.net "${part.oemNumber}"`)}`},
    {name: 'AutoPartsPrime', url: `https://www.google.com/search?q=${encodeURIComponent(`site:autopartsprime.com "${part.oemNumber}"`)}`},
    {name: 'eBay', url: `https://www.ebay.com/sch/i.html?_nkw=${q}`},
  ];
}

function PartGlyph({part}: {part: SixthGenPart}) {
  return (
    <span className={`pg6-glyph pg6-glyph--${part.group}`} aria-hidden="true">
      {part.group === 'fan' ? '✣' : part.group === 'hose' ? '∿' : part.group === 'hardware' ? '⌁' : part.group === 'mount' ? '⌐' : part.group === 'reservoir' ? '▱' : '▦'}
    </span>
  );
}

function StateButtons({value, onChange}: {value: SixthGenPartState; onChange: (state: SixthGenPartState) => void}) {
  const values: SixthGenPartState[] = ['need', 'have', 'inspect', 'not-sure'];
  return (
    <div className="pg6-state-buttons" role="group" aria-label="Part state">
      {values.map((item) => (
        <button key={item} type="button" className={value === item ? 'active' : ''} onClick={() => onChange(item)}>{stateLabels[item]}</button>
      ))}
    </div>
  );
}

function dataSearchUrl(query: string) {
  return `https://www.google.com/search?q=${encodeURIComponent(query)}`;
}

export function PartGraphSixthGen() {
  const [year, setYear] = useState<number>(2000);
  const [configurations, setConfigurations] = useState<HondaManualConfiguration[]>([]);
  const [configurationKey, setConfigurationKey] = useState('');
  const [configurationLoading, setConfigurationLoading] = useState(false);
  const [block, setBlock] = useState<RepairBlock>('cooling');
  const [targetPartId, setTargetPartId] = useState('radiator');
  const [states, setStates] = useState<Record<string, SixthGenPartState>>({});
  const [photoUrl, setPhotoUrl] = useState('');
  const [photoName, setPhotoName] = useState('');
  const [savedAt, setSavedAt] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setConfigurationLoading(true);
    fetchHondaManualConfigurations(year, 'Civic')
      .then((result) => {
        if (cancelled) return;
        setConfigurations(result.options);
        setConfigurationKey((current) => result.options.some((item) => item.value === current) ? current : (result.options[0]?.value ?? ''));
      })
      .finally(() => { if (!cancelled) setConfigurationLoading(false); });
    return () => { cancelled = true; };
  }, [year]);

  useEffect(() => () => {
    if (photoUrl) URL.revokeObjectURL(photoUrl);
  }, [photoUrl]);

  const selectedConfiguration = configurations.find((item) => item.value === configurationKey) ?? null;
  const resolution = useMemo(() => {
    if (!selectedConfiguration) return null;
    return resolveCivicSixthGenCooling({
      year,
      bodyTrim: selectedConfiguration.label,
      emissionTransmission: selectedConfiguration.secondary ?? '',
      sourceUrl: selectedConfiguration.sourceUrl,
    });
  }, [year, selectedConfiguration]);

  const published = block === 'cooling' && resolution?.status === 'verified';
  const parts = published && resolution ? resolution.parts : [];
  const targetOptions = parts
    .filter((part) => part.group !== 'hardware')
    .map((part) => ({value: part.id, label: part.name, secondary: `OEM ${part.oemNumber}`}));

  useEffect(() => {
    if (!published || !resolution) return;
    const next = Object.fromEntries(resolution.parts.map((part) => [part.id, sixthGenDefaultState(part)]));
    try {
      const raw = localStorage.getItem(`${STORAGE_PREFIX}${configurationKey}`);
      setStates(raw ? {...next, ...(JSON.parse(raw) as Record<string, SixthGenPartState>)} : next);
    } catch {
      setStates(next);
    }
    setTargetPartId((current) => resolution.parts.some((part) => part.id === current) ? current : 'radiator');
    setSavedAt('');
  }, [published, resolution, configurationKey]);

  const needParts = parts.filter((part) => states[part.id] === 'need');
  const unresolved = parts.filter((part) => states[part.id] === 'not-sure').length;

  const changeState = (partId: string, state: SixthGenPartState) => setStates((current) => ({...current, [partId]: state}));

  const save = () => {
    if (!published) return;
    localStorage.setItem(`${STORAGE_PREFIX}${configurationKey}`, JSON.stringify(states));
    setSavedAt(new Date().toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'}));
  };

  const reset = () => {
    if (!resolution || resolution.status !== 'verified') return;
    const next = Object.fromEntries(resolution.parts.map((part) => [part.id, sixthGenDefaultState(part)]));
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

  const unavailableQuery = selectedConfiguration
    ? `${year} Honda Civic ${selectedConfiguration.label} ${selectedConfiguration.secondary ?? ''} OEM ${block} parts diagram part numbers`
    : `${year} Honda Civic OEM ${block} parts diagram part numbers`;

  const copyResearchPrompt = async () => {
    const prompt = `Research exact OEM part numbers for ${unavailableQuery}. Use exact vehicle-configuration catalog sources. Do not borrow parts from another trim or transmission. Return source URLs, supersessions, quantities, supplier variants and unresolved ambiguity. Do not mark anything verified without corroborating exact fitment.`;
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  const yearOptions = [...CIVIC_SIXTH_GEN_YEARS].reverse().map((item) => ({value: String(item), label: String(item)}));
  const configurationOptions = configurations.map((item) => ({value: item.value, label: item.label, secondary: item.secondary}));

  return (
    <main className="pg6-shell">
      <header className="pg6-header">
        <a className="pg6-brand" href="#/"><span><Wrench size={18}/></span><strong>PARTGRAPH</strong><small>Complete repair parts</small></a>
        <div className="pg6-publish"><ShieldCheck size={14}/><span><strong>Published stage</strong>{CIVIC_SIXTH_GEN_LABEL} · front cooling</span></div>
        <nav><a href="#/8th-gen">2009 Hybrid data</a><button type="button" onClick={save} disabled={!published}>{savedAt ? `Saved ${savedAt}` : 'Save repair'}</button></nav>
      </header>

      <section className="pg6-hero">
        <div>
          <span className="pg6-kicker">GENERATION 6 · STAGE 1</span>
          <h1>Rebuild the complete cooling assembly.</h1>
          <p>Choose the exact 1996–2000 Civic configuration. PartGraph loads only the OEM identities verified for that body/trim and transmission; everything else stays marked unavailable instead of being guessed.</p>
        </div>
        <aside className="pg6-qr"><img src={QR_URL} alt="QR code to open PartGraph on a phone"/><span><Smartphone size={16}/><strong>Open on phone</strong><small>Take photos beside the car.</small></span></aside>
      </section>

      <section className="pg6-flow">
        <div className="pg6-flow-heading"><span>1</span><div><strong>Vehicle</strong><small>Exact catalog configuration</small></div></div>
        <div className="pg6-select-grid">
          <PartGraphSelect label="Make" value="Honda" options={[{value: 'Honda', label: 'Honda'}]} onChange={() => undefined}/>
          <PartGraphSelect label="Generation" value="6" options={[{value: '6', label: '6th Generation', secondary: '1996–2000 Civic'}]} onChange={() => undefined}/>
          <PartGraphSelect label="Year" value={String(year)} options={yearOptions} onChange={(value) => setYear(Number(value))}/>
          <PartGraphSelect label="Model" value="Civic" options={[{value: 'Civic', label: 'Civic'}]} onChange={() => undefined}/>
          <PartGraphSelect label={configurationLoading ? 'Exact trim · loading' : 'Exact trim'} value={configurationKey} options={configurationOptions} onChange={setConfigurationKey} placeholder="Choose exact configuration"/>
        </div>
        {selectedConfiguration ? <p className="pg6-source-line"><CheckCircle2 size={13}/>Catalog identity: <strong>{selectedConfiguration.label}</strong> · {selectedConfiguration.secondary} <a href={selectedConfiguration.sourceUrl} target="_blank" rel="noreferrer">source <ExternalLink size={11}/></a></p> : null}

        <div className="pg6-flow-heading"><span>2</span><div><strong>Repair target</strong><small>Block → sub-block → part</small></div></div>
        <div className="pg6-select-grid pg6-select-grid--repair">
          <PartGraphSelect label="Block" value={block} options={blockOptions} onChange={(value) => setBlock(value as RepairBlock)}/>
          <PartGraphSelect label="Sub-block" value={block === 'cooling' ? 'front-cooling' : ''} options={block === 'cooling' ? [{value: 'front-cooling', label: 'Front cooling / radiator'}] : [{value: '', label: 'Data unavailable', disabled: true}]} onChange={() => undefined}/>
          <PartGraphSelect label="Target part" value={published ? targetPartId : ''} options={published ? targetOptions : [{value: '', label: 'Data unavailable', disabled: true}]} onChange={setTargetPartId}/>
        </div>

        {published && resolution ? (
          <div className="pg6-ready"><ShieldCheck size={16}/><span><strong>Verified data loaded</strong>{resolution.configurationLabel} · radiator <code>{resolution.radiatorNumber}</code>{resolution.alternateRadiatorNumbers?.length ? ` · supplier alternative ${resolution.alternateRadiatorNumbers.join(', ')}` : ''}</span></div>
        ) : (
          <div className="pg6-unavailable">
            <AlertTriangle size={22}/>
            <div><span>DATA UNAVAILABLE</span><h2>We have not published this exact repair data yet.</h2><p>{block === 'cooling' ? (resolution?.note ?? 'Choose an exact Civic catalog configuration.') : `6th-generation ${block.replace('-', ' ')} data is a later stage. PartGraph will not reuse cooling or 2009 parts.`}</p>
              <div className="pg6-unavailable-actions">
                {selectedConfiguration ? <a href={selectedConfiguration.sourceUrl} target="_blank" rel="noreferrer"><ExternalLink size={14}/>Open exact vehicle catalog</a> : null}
                <a href={dataSearchUrl(unavailableQuery)} target="_blank" rel="noreferrer"><Search size={14}/>Search OEM web sources</a>
                <button type="button" onClick={() => void copyResearchPrompt()}><Clipboard size={14}/>{copied ? 'AI research prompt copied' : 'Copy AI research prompt'}</button>
              </div>
              <small>AI/web research is deliberately on-demand so known configurations use zero LLM tokens. Any new result must be verified before it becomes published mechanical truth.</small>
            </div>
          </div>
        )}
      </section>

      {published && resolution ? (
        <>
          <section className="pg6-camera">
            <div className="pg6-camera-copy"><Camera size={24}/><div><span>PHOTO HELP</span><h2>If you’re not sure what the parts are called, let us take a look.</h2><p>Use the phone camera now. Stage 1 keeps the photo on-device; recognition will later compare it only against this exact vehicle/assembly candidate set.</p></div></div>
            {photoUrl ? <div className="pg6-photo"><img src={photoUrl} alt="Selected car part"/><span><strong>{photoName}</strong><small>Local preview only</small></span><label>Retake<input type="file" accept="image/*" capture="environment" onChange={(event) => takePhoto(event.target.files?.[0])}/></label></div> : <label className="pg6-camera-button"><Camera size={17}/>Take or choose part photo<input type="file" accept="image/*" capture="environment" onChange={(event) => takePhoto(event.target.files?.[0])}/></label>}
          </section>

          <section className="pg6-assembly">
            <div className="pg6-section-title"><div><span>3 · ASSEMBLY CHECK</span><h2>What do you still need?</h2><p>{parts.length} source-backed component records in this Stage 1 cooling packet. Tap the OEM diagram link whenever the name is not enough.</p></div><div className="pg6-count"><strong>{unresolved}</strong><small>not sure</small></div></div>
            <div className="pg6-parts">
              {parts.map((part) => {
                const state = states[part.id] ?? sixthGenDefaultState(part);
                return (
                  <article className={`pg6-part pg6-part--${state} ${part.id === targetPartId ? 'target' : ''}`} key={part.id}>
                    <a className="pg6-part-visual" href={part.sourceUrl} target="_blank" rel="noreferrer" title="Open OEM catalog diagram"><PartGlyph part={part}/><span><ImageIcon size={11}/>OEM diagram</span></a>
                    <div className="pg6-part-copy">
                      <div className="pg6-meta">{part.id === targetPartId ? <b>Target</b> : null}<em>Verified</em><code>{part.oemNumber}</code>{part.quantity > 1 ? <i>×{part.quantity}</i> : null}</div>
                      <h3>{part.name}</h3>
                      <p>{part.note}</p>
                      {part.alternateNumbers?.length ? <small className="pg6-alt">Alternate / supplier number: {part.alternateNumbers.join(', ')}</small> : null}
                      {part.replacedNumbers?.length ? <small className="pg6-alt">Replaces / older number: {part.replacedNumbers.join(', ')}</small> : null}
                    </div>
                    <StateButtons value={state} onChange={(next) => changeState(part.id, next)}/>
                  </article>
                );
              })}
            </div>
            <div className="pg6-sticky"><span><strong>{needParts.length} to find</strong><small>Exact OEM identities only</small></span><a href="#pg6-buy"><ShoppingCart size={15}/>Purchase links</a><button type="button" onClick={reset}><RotateCcw size={14}/>Reset</button></div>
          </section>

          <section className="pg6-buy" id="pg6-buy">
            <div className="pg6-section-title compact"><div><span>4 · PARTS TO BUY</span><h2>{needParts.length ? `${needParts.length} selected item${needParts.length === 1 ? '' : 's'}` : 'Mark a part Need to shop it'}</h2><p>Five search paths begin with the verified OEM number. The store never decides fitment.</p></div><PackageCheck size={28}/></div>
            <div className="pg6-buy-list">
              {needParts.map((part) => (
                <article key={part.id} className="pg6-buy-card"><PartGlyph part={part}/><div><strong>{part.name}{part.quantity > 1 ? ` ×${part.quantity}` : ''}</strong><code>{part.oemNumber}</code></div><div className="pg6-links">{productSearchLinks(part).map((link) => <a key={link.name} href={link.url} target="_blank" rel="noreferrer">{link.name}<ExternalLink size={11}/></a>)}</div></article>
              ))}
            </div>
          </section>

          <section className="pg6-provenance">
            <ShieldCheck size={18}/><div><strong>Stage 1 source boundary</strong><p>Exact configuration identity comes from the static Honda catalog index already in this repository. Cooling part numbers are published only where this stage has an explicit rule and source page. Service torque, fluid quantity and repair procedure are not inferred here.</p><div>{resolution.radiatorSourceUrl ? <a href={resolution.radiatorSourceUrl} target="_blank" rel="noreferrer">Radiator catalog <ExternalLink size={11}/></a> : null}{resolution.hoseSourceUrl ? <a href={resolution.hoseSourceUrl} target="_blank" rel="noreferrer">Hose / mount catalog <ExternalLink size={11}/></a> : null}</div></div>
          </section>
        </>
      ) : null}

      <footer className="pg6-footer">6th Generation Civic is being published one assembly at a time. Known data is cached/static; missing data triggers explicit research instead of a guessed answer.</footer>
    </main>
  );
}
