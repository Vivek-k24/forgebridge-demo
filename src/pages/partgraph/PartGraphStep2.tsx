import {useEffect, useMemo, useState} from 'react';
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  ExternalLink,
  Image as ImageIcon,
  PackageCheck,
  RotateCcw,
  Save,
  ScanLine,
  ShieldCheck,
  ShoppingCart,
  Wrench,
  X,
} from 'lucide-react';
import {commerceSources, type PartNode, type PartState} from '../../data/partGraphDemo';
import {partImageById} from '../../data/partGraphImages';
import {
  initialStatesForGraph,
  type RepairBlockId,
  type RepairGraphDefinition,
} from '../../data/partGraphSystems';
import {
  demoHondaIdentity,
  decodeHondaVin,
  fetchHondaModels,
  hasVerifiedDemoCoverage,
  hondaModelYears,
  identityTrimLabel,
  isCompleteVin,
  manualHondaIdentity,
  normalizeVin,
  type HondaModelOption,
  type HondaVehicleIdentity,
} from '../../lib/hondaVehicleService';
import {
  fetchHondaManualConfigurations,
  type HondaManualConfiguration,
  type HondaManualConfigurationResult,
} from '../../lib/hondaManualConfigurationService';
import {
  PARTGRAPH_DB_VERSION,
  hardwareForPart,
  listRepairBlocks,
  listSubBlocks,
  listTargetParts,
  orphanHardware,
  readRepairGraph,
  visibleAssemblyParts,
} from '../../lib/partGraphRepository';
import {PartGraphSelect, type PartGraphSelectOption} from './PartGraphSelect';
import '../../styles/partgraph-step2.css';
import '../../styles/partgraph-consumer.css';

const APP_URL = 'https://vivek-k24.github.io/forgebridge-demo/#/';
const QR_URL = `https://api.qrserver.com/v1/create-qr-code/?size=132x132&margin=6&data=${encodeURIComponent(APP_URL)}`;
const STORAGE_PREFIX = 'partgraph.step2.state.';

const sellerDomains: Record<string, string> = {
  hondapartsnow: 'hondapartsnow.com',
  hondafactoryparts: 'hondafactoryparts.com',
  hondapartsonline: 'hondapartsonline.net',
  autopartsprime: 'autopartsprime.com',
};

const stateLabels: Record<PartState, string> = {
  need: 'Need',
  have: 'Have',
  inspect: 'Inspect',
  'not-sure': 'Not sure',
};

function loadStates(graph: RepairGraphDefinition): Record<string, PartState> {
  const base = initialStatesForGraph(graph);
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}${graph.id}`);
    if (!raw) return base;
    const saved = JSON.parse(raw) as Record<string, PartState>;
    const valid = new Set(graph.parts.map((part) => part.id));
    return Object.fromEntries(Object.entries({...base, ...saved}).filter(([id]) => valid.has(id)));
  } catch {
    return base;
  }
}

function sellerUrl(part: PartNode, source: {id: string; name: string}) {
  const direct = part.purchaseLinks?.find((link) => link.name === source.name);
  if (direct) return direct.url;
  if (!part.oemNumber || part.source.status !== 'verified') return null;
  if (source.id === 'ebay') return `https://www.ebay.com/sch/i.html?_nkw=${encodeURIComponent(part.oemNumber)}`;
  const domain = sellerDomains[source.id];
  if (!domain) return null;
  return `https://www.google.com/search?q=${encodeURIComponent(`site:${domain} "${part.oemNumber}"`)}`;
}

function hardwareKind(name: string) {
  const value = name.toLowerCase();
  if (value.includes('o-ring') || value.includes('gasket') || value.includes('seal') || value.includes('washer')) return 'ring';
  if (value.includes('clip') || value.includes('clamp')) return 'clip';
  if (value.includes('screw')) return 'screw';
  if (value.includes('bolt')) return 'bolt';
  if (value.includes('cap')) return 'cap';
  return 'hardware';
}

function HardwareGlyph({name}: {name: string}) {
  const kind = hardwareKind(name);
  return (
    <span className={`pg2-hardware-glyph pg2-hardware-glyph--${kind}`} aria-hidden="true">
      {kind === 'ring' ? (
        <svg viewBox="0 0 36 36"><circle cx="18" cy="18" r="10"/><circle className="inner" cx="18" cy="18" r="5"/></svg>
      ) : kind === 'clip' ? (
        <svg viewBox="0 0 36 36"><path d="M10 7v14c0 6 3 9 8 9s8-3 8-9V7"/><path className="thin" d="M14 7v14c0 3 1 5 4 5s4-2 4-5V7"/></svg>
      ) : kind === 'cap' ? (
        <svg viewBox="0 0 36 36"><path d="M10 14h16v12H10z"/><path className="thin" d="M8 14h20M12 10h12v4"/></svg>
      ) : (
        <svg viewBox="0 0 36 36"><path d="M8 11l5-5h7l5 5-5 5h-7z"/><path d="M19 14l9 14"/><path className="thin" d="M19 18l5-2M21 22l5-2M23 26l4-2"/></svg>
      )}
    </span>
  );
}

function PartVisual({part, onPreview}: {part: PartNode; onPreview: (part: PartNode) => void}) {
  const image = partImageById[part.id];
  if (image) {
    return (
      <button className="pg2-part-visual" type="button" onClick={() => onPreview(part)} aria-label={`View ${part.name}`}>
        <img src={image.url} alt={image.alt} loading="lazy" referrerPolicy="no-referrer" />
        <span>View</span>
        <span className="pg2-hover-image" aria-hidden="true"><img src={image.url} alt="" /></span>
      </button>
    );
  }

  return (
    <a className="pg2-part-visual pg2-part-visual--diagram" href={part.source.url} target="_blank" rel="noreferrer" title="Open verified catalog source">
      <ImageIcon size={21} />
      <small>Catalog</small>
    </a>
  );
}

function StateButtons({value, onChange, compact = false}: {value: PartState; onChange: (state: PartState) => void; compact?: boolean}) {
  const choices: PartState[] = compact ? ['need', 'have', 'inspect'] : ['need', 'have', 'inspect', 'not-sure'];
  return (
    <div className={`pg2-state-buttons ${compact ? 'compact' : ''}`}>
      {choices.map((choice) => (
        <button key={choice} type="button" className={value === choice ? 'active' : ''} onClick={() => onChange(choice)}>{stateLabels[choice]}</button>
      ))}
    </div>
  );
}

function toConfigurationOptions(configurations: HondaManualConfiguration[], loading: boolean): PartGraphSelectOption[] {
  if (configurations.length) {
    return configurations.map((configuration) => ({
      value: configuration.value,
      label: configuration.label,
      secondary: configuration.secondary,
    }));
  }
  return [{
    value: '',
    label: loading ? 'Loading trims…' : 'No published repair trim yet',
    disabled: loading,
    secondary: loading
      ? 'Checking published Honda vehicle coverage.'
      : 'PartGraph will not guess an exact repair graph.',
  }];
}

export function PartGraphStep2() {
  const blocks = useMemo(() => listRepairBlocks(), []);
  const [mode, setMode] = useState<'manual' | 'vin'>('manual');
  const [year, setYear] = useState(2009);
  const [model, setModel] = useState('Civic');
  const [trim, setTrim] = useState('');
  const [models, setModels] = useState<HondaModelOption[]>([{id: 1, name: 'Civic'}]);
  const [modelLoading, setModelLoading] = useState(false);
  const [configurations, setConfigurations] = useState<HondaManualConfiguration[]>([]);
  const [configurationLoading, setConfigurationLoading] = useState(false);
  const [configurationSource, setConfigurationSource] = useState<HondaManualConfigurationResult | null>(null);
  const [vin, setVin] = useState('');
  const [vinLoading, setVinLoading] = useState(false);
  const [vehicleError, setVehicleError] = useState('');
  const [vehicle, setVehicle] = useState<HondaVehicleIdentity>(demoHondaIdentity);
  const [blockId, setBlockId] = useState<RepairBlockId>('cooling');
  const firstGraph = useMemo(() => listSubBlocks('cooling')[0], []);
  const [graphId, setGraphId] = useState(firstGraph.id);
  const [targetPartId, setTargetPartId] = useState(firstGraph.defaultTargetPartId);
  const [states, setStates] = useState<Record<string, PartState>>(() => loadStates(firstGraph));
  const [showResolved, setShowResolved] = useState(false);
  const [photoUrl, setPhotoUrl] = useState('');
  const [photoName, setPhotoName] = useState('');
  const [previewPart, setPreviewPart] = useState<PartNode | null>(null);
  const [savedAt, setSavedAt] = useState('');

  const graph = readRepairGraph(graphId);
  const subBlocks = listSubBlocks(blockId);
  const targetParts = listTargetParts(graph);
  const assemblyParts = visibleAssemblyParts(graph);
  const unsupportedHardware = orphanHardware(graph);
  const coverage = hasVerifiedDemoCoverage(vehicle);
  const targetPart = targetParts.find((part) => part.id === targetPartId) ?? targetParts[0];

  const displayParts = useMemo(() => {
    const ordered = [...assemblyParts].sort((a, b) => {
      if (a.id === targetPartId) return -1;
      if (b.id === targetPartId) return 1;
      return a.name.localeCompare(b.name);
    });
    return showResolved ? ordered : ordered.filter((part) => states[part.id] !== 'have' || part.id === targetPartId);
  }, [assemblyParts, showResolved, states, targetPartId]);

  const needs = graph.parts.filter((part) => states[part.id] === 'need');
  const unresolvedCount = graph.parts.filter((part) => states[part.id] === 'not-sure').length;
  const resolvedVisibleCount = assemblyParts.filter((part) => states[part.id] === 'have').length;

  useEffect(() => {
    let cancelled = false;
    setModelLoading(true);
    fetchHondaModels(year)
      .then((result) => {
        if (cancelled) return;
        setModels(result.models);
        setModel((currentModel) => {
          if (result.models.some((item) => item.name.toLowerCase() === currentModel.toLowerCase())) return currentModel;
          setTrim('');
          return result.models[0]?.name ?? '';
        });
      })
      .finally(() => {
        if (!cancelled) setModelLoading(false);
      });
    return () => { cancelled = true; };
  }, [year]);

  useEffect(() => {
    if (mode !== 'manual' || !model) return;
    let cancelled = false;
    setConfigurationLoading(true);
    setConfigurationSource(null);

    fetchHondaManualConfigurations(year, model)
      .then((result) => {
        if (cancelled) return;
        setConfigurations(result.options);
        setConfigurationSource(result);
        setTrim((currentTrim) => {
          if (result.options.some((option) => option.value === currentTrim)) return currentTrim;
          const hybrid = result.options.find((option) => option.trim.toLowerCase() === 'hybrid');
          return hybrid?.value ?? result.options[0]?.value ?? '';
        });
      })
      .finally(() => {
        if (!cancelled) setConfigurationLoading(false);
      });

    return () => { cancelled = true; };
  }, [mode, year, model]);

  useEffect(() => {
    if (mode !== 'manual' || !model) return;
    const selectedConfiguration = configurations.find((option) => option.value === trim);
    setVehicle(manualHondaIdentity(year, model, selectedConfiguration?.trim ?? ''));
    setVehicleError('');
  }, [mode, year, model, trim, configurations]);

  useEffect(() => () => {
    if (photoUrl) URL.revokeObjectURL(photoUrl);
  }, [photoUrl]);

  const activateGraph = (next: RepairGraphDefinition) => {
    setGraphId(next.id);
    setBlockId(next.blockId);
    setTargetPartId(next.defaultTargetPartId);
    setStates(loadStates(next));
    setShowResolved(false);
    setSavedAt('');
  };

  const selectBlock = (value: string) => {
    const nextBlock = value as RepairBlockId;
    const nextGraph = listSubBlocks(nextBlock)[0];
    if (nextGraph) activateGraph(nextGraph);
  };

  const changeState = (partId: string, state: PartState) => {
    setStates((current) => ({...current, [partId]: state}));
  };

  const saveRepair = () => {
    localStorage.setItem(`${STORAGE_PREFIX}${graph.id}`, JSON.stringify(states));
    setSavedAt(new Date().toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'}));
  };

  const resetRepair = () => {
    const reset = initialStatesForGraph(graph);
    setStates(reset);
    localStorage.removeItem(`${STORAGE_PREFIX}${graph.id}`);
    setShowResolved(false);
    setSavedAt('');
  };

  const decodeVin = async () => {
    const normalized = normalizeVin(vin);
    setVin(normalized);
    setVehicleError('');
    if (!isCompleteVin(normalized)) {
      setVehicleError('Enter all 17 VIN characters. VINs do not use I, O or Q.');
      return;
    }
    setVinLoading(true);
    try {
      const decoded = await decodeHondaVin(normalized);
      setVehicle(decoded);
      setYear(decoded.year);
      setModel(decoded.model);
    } catch (error) {
      setVehicleError(error instanceof Error ? error.message : 'VIN lookup failed.');
    } finally {
      setVinLoading(false);
    }
  };

  const onPhoto = (file?: File) => {
    if (!file) return;
    if (photoUrl) URL.revokeObjectURL(photoUrl);
    setPhotoUrl(URL.createObjectURL(file));
    setPhotoName(file.name);
  };

  const yearOptions = hondaModelYears().map((item) => ({value: String(item), label: String(item)}));
  const modelOptions = models.map((item) => ({value: item.name, label: item.name}));
  const configurationOptions = toConfigurationOptions(configurations, configurationLoading);
  const blockOptions = blocks.map((block) => ({value: block.id, label: block.label, secondary: block.description}));
  const subBlockOptions = subBlocks.map((item) => ({value: item.id, label: item.label, secondary: item.summary}));
  const targetOptions = targetParts.map((part) => ({value: part.id, label: part.name, secondary: part.oemNumber || 'Service item'}));

  return (
    <main className="pg2-shell">
      <header className="pg2-header">
        <a className="pg2-brand" href="#/">
          <span className="pg2-brand-mark"><Wrench size={18}/></span>
          <span><strong>PARTGRAPH</strong><small>Complete repair parts</small></span>
        </a>
        <div className="pg2-header-status"><ShieldCheck size={14}/>Honda-first verified graph <code>v{PARTGRAPH_DB_VERSION}</code></div>
        <button className="pg2-save" type="button" onClick={saveRepair} disabled={!coverage}><Save size={14}/>{savedAt ? `Saved ${savedAt}` : 'Save repair'}</button>
      </header>

      <section className="pg2-hero">
        <div>
          <span className="pg2-kicker">HONDA REPAIR BUILDER</span>
          <h1>Find the whole repair, not one lonely part.</h1>
          <p>Select the exact car, repair area and main part. We keep the screws, seals, clips and washers attached to the part they actually belong to.</p>
        </div>
        <aside className="pg2-qr">
          <img src={QR_URL} alt="QR code to open PartGraph on a phone"/>
          <span><strong>Use your phone</strong><small>Scan to take part photos beside the car.</small></span>
        </aside>
      </section>

      <section className="pg2-workflow">
        <div className="pg2-workflow-title">
          <div><span>STEP 1</span><strong>Vehicle</strong></div>
          <div className="pg2-mode">
            <button type="button" className={mode === 'manual' ? 'active' : ''} onClick={() => setMode('manual')}>Manual selection</button>
            <button type="button" className={mode === 'vin' ? 'active' : ''} onClick={() => setMode('vin')}>VIN lookup (optional)</button>
          </div>
        </div>

        {mode === 'manual' ? (
          <>
            <div className="pg2-vehicle-row">
              <PartGraphSelect label="Year" value={String(year)} options={yearOptions} onChange={(value) => {setYear(Number(value)); setTrim('');}}/>
              <PartGraphSelect label={modelLoading ? 'Model · loading' : 'Model'} value={model} options={modelOptions} onChange={(value) => {setModel(value); setTrim('');}} placeholder="Choose Honda model"/>
              <PartGraphSelect label={configurationLoading ? 'Trim · loading' : 'Trim'} value={trim} options={configurationOptions} onChange={setTrim} placeholder="Choose trim"/>
            </div>
            <p className="pg2-scope-note">
              <CheckCircle2 size={13}/>
              <span>{configurationSource?.note ?? 'Choose the trim you recognize from the vehicle badge or owner documentation.'}</span>
              {configurationSource?.sourceUrl ? <a href={configurationSource.sourceUrl} target="_blank" rel="noreferrer">Vehicle source <ExternalLink size={11}/></a> : null}
            </p>
          </>
        ) : (
          <div className="pg2-vin-row">
            <label><span>17-character VIN</span><input value={vin} onChange={(event) => setVin(normalizeVin(event.target.value))} maxLength={17} placeholder="2HGFA…"/></label>
            <button type="button" onClick={() => void decodeVin()} disabled={vinLoading}><ScanLine size={15}/>{vinLoading ? 'Decoding…' : 'Decode VIN'}</button>
            <small>NHTSA vPIC public decoder · optional second path · no model tokens</small>
          </div>
        )}

        {vehicleError ? <div className="pg2-error"><AlertTriangle size={14}/>{vehicleError}</div> : null}

        <div className="pg2-current-vehicle">
          <span className={coverage ? 'ready' : 'blocked'}>{coverage ? <ShieldCheck size={13}/> : <AlertTriangle size={13}/>} {coverage ? 'Repair graph matched' : 'Vehicle identified · no verified repair graph'}</span>
          <strong>{vehicle.year} Honda {vehicle.model}</strong>
          <small>{identityTrimLabel(vehicle)}</small>
        </div>

        <div className={`pg2-step2 ${coverage ? '' : 'disabled'}`}>
          <div className="pg2-workflow-title"><div><span>STEP 2</span><strong>Repair</strong></div><small>Block → sub-block → target part</small></div>
          <div className="pg2-repair-row">
            <PartGraphSelect label="Block" value={blockId} options={blockOptions} onChange={selectBlock} disabled={!coverage}/>
            <PartGraphSelect label="Sub-block" value={graph.id} options={subBlockOptions} onChange={(value) => activateGraph(readRepairGraph(value))} disabled={!coverage}/>
            <PartGraphSelect label="Target part" value={targetPart?.id ?? ''} options={targetOptions} onChange={setTargetPartId} disabled={!coverage}/>
          </div>
          {coverage ? <p className="pg2-scope-note"><CheckCircle2 size={13}/>Verified repair graph loaded for {vehicle.year} Honda {vehicle.model} · {identityTrimLabel(vehicle)}.</p> : <p className="pg2-scope-note blocked"><AlertTriangle size={13}/>We do not substitute another trim's parts graph. Vehicle browsing can continue, but mechanical parts stay locked until this exact configuration has verified coverage.</p>}
        </div>
      </section>

      {coverage ? (
        <>
          <section className="pg2-camera">
            <div className="pg2-camera-copy"><Camera size={24}/><div><span>PHOTO HELP</span><h2>If you’re not sure what the parts are called, let us take a look.</h2><p>Take a photo now. This build keeps it on your device and pins it beside the verified assembly while you compare parts.</p></div></div>
            {photoUrl ? (
              <div className="pg2-camera-preview"><img src={photoUrl} alt="Your part"/><span><strong>{photoName}</strong><small>On-device preview</small></span><label>Retake<input type="file" accept="image/*" capture="environment" onChange={(event) => onPhoto(event.target.files?.[0])}/></label></div>
            ) : (
              <label className="pg2-camera-action"><Camera size={16}/>Take or choose photo<input type="file" accept="image/*" capture="environment" onChange={(event) => onPhoto(event.target.files?.[0])}/></label>
            )}
          </section>

          {graph.warning ? <div className="pg2-warning"><AlertTriangle size={16}/><span><strong>Safety boundary</strong>{graph.warning}</span></div> : null}

          <section className="pg2-assembly">
            <div className="pg2-section-title">
              <div><span>STEP 3 · ASSEMBLY CHECK</span><h2>What do you still need?</h2><p>{targetPart?.name} is first. Fasteners are nested inside their parent part instead of taking over the page.</p></div>
              <div className="pg2-assembly-count"><strong>{unresolvedCount}</strong><small>unanswered</small></div>
            </div>

            <div className="pg2-display-tools">
              <span>{displayParts.length} parts shown · {resolvedVisibleCount} marked have</span>
              <button type="button" onClick={() => setShowResolved((value) => !value)}>{showResolved ? 'Hide completed' : 'Show all parts'}</button>
            </div>

            <div className="pg2-part-list">
              {displayParts.map((part) => {
                const state = states[part.id] ?? 'not-sure';
                const hardware = hardwareForPart(graph, part.id);
                return (
                  <article className={`pg2-part-card pg2-part-card--${state} ${part.id === targetPartId ? 'target' : ''}`} key={part.id}>
                    <PartVisual part={part} onPreview={setPreviewPart}/>
                    <div className="pg2-part-copy">
                      <div className="pg2-part-meta">
                        {part.id === targetPartId ? <b>Target</b> : null}
                        <span className={part.source.status === 'verified' ? 'verified' : 'service'}>{part.source.status === 'verified' ? 'Verified' : 'Service item'}</span>
                        {part.oemNumber ? <code>{part.oemNumber}</code> : null}
                      </div>
                      <h3>{part.name}{part.quantity > 1 ? ` ×${part.quantity}` : ''}</h3>
                      <p>{part.description}</p>
                      {hardware.length ? (
                        <div className="pg2-hardware-strip">
                          <span className="pg2-hardware-title">Attached hardware</span>
                          {hardware.map(({part: item, relation, relationLabel}) => {
                            const hardwareState = states[item.id] ?? 'not-sure';
                            return (
                              <div className="pg2-hardware-row" key={`${part.id}-${item.id}-${relation.type}`}>
                                <HardwareGlyph name={item.name}/>
                                <span className="pg2-hardware-copy"><strong>{item.name}{item.quantity > 1 ? ` ×${item.quantity}` : ''}</strong><small>{relationLabel}{item.oemNumber ? ` · OEM ${item.oemNumber}` : ''}</small></span>
                                <StateButtons value={hardwareState} compact onChange={(next) => changeState(item.id, next)}/>
                              </div>
                            );
                          })}
                        </div>
                      ) : null}
                    </div>
                    <StateButtons value={state} onChange={(next) => changeState(part.id, next)}/>
                  </article>
                );
              })}
            </div>

            {unsupportedHardware.length ? <div className="pg2-data-warning"><AlertTriangle size={14}/>{unsupportedHardware.length} catalog hardware item(s) are not yet attached to a parent relation and are intentionally not hidden.</div> : null}

            <div className="pg2-sticky-summary">
              <span><strong>{needs.length} to find</strong><small>includes hardware marked Need</small></span>
              <a href="#pg2-buy"><ShoppingCart size={15}/>See purchase links</a>
              <button type="button" onClick={resetRepair}><RotateCcw size={14}/>Reset</button>
            </div>
          </section>

          <section className="pg2-buy" id="pg2-buy">
            <div className="pg2-section-title compact"><div><span>PARTS TO BUY</span><h2>{needs.length ? `${needs.length} selected item${needs.length === 1 ? '' : 's'}` : 'Nothing marked Need yet'}</h2><p>Five paths are generated only after the OEM identity is known. Store fitment badges do not override the verified graph.</p></div><PackageCheck size={28}/></div>
            <div className="pg2-buy-list">
              {needs.map((part) => (
                <article className="pg2-buy-card" key={part.id}>
                  <PartVisual part={part} onPreview={setPreviewPart}/>
                  <div className="pg2-buy-info"><strong>{part.name}{part.quantity > 1 ? ` ×${part.quantity}` : ''}</strong>{part.oemNumber ? <code>{part.oemNumber}</code> : <span>Service item · no verified OEM number</span>}<small>{part.source.label}</small></div>
                  <div className="pg2-seller-links">
                    {commerceSources.map((source) => {
                      const url = sellerUrl(part, source);
                      return url ? <a key={source.id} href={url} target="_blank" rel="noreferrer"><span>{source.name}</span><ExternalLink size={12}/></a> : <span className="disabled" key={source.id}>{source.name}</span>;
                    })}
                  </div>
                </article>
              ))}
            </div>
          </section>
        </>
      ) : (
        <section className="pg2-stop"><AlertTriangle size={24}/><div><h2>No guessing across vehicle configurations.</h2><p>The interface stays usable, but mechanical parts remain locked until the selected Honda matches a published graph.</p></div></section>
      )}

      <footer className="pg2-footer"><ShieldCheck size={14}/>Mechanical facts are source-backed. Product photos are reference media only. Torque, procedures and fitment are not invented from language-model output.</footer>

      {previewPart ? (
        <div className="pg2-modal" role="dialog" aria-modal="true" aria-label={`Preview ${previewPart.name}`} onClick={() => setPreviewPart(null)}>
          <div className="pg2-modal-card" onClick={(event) => event.stopPropagation()}>
            <button type="button" className="pg2-modal-close" onClick={() => setPreviewPart(null)}><X size={18}/></button>
            {partImageById[previewPart.id] ? <img src={partImageById[previewPart.id].url} alt={partImageById[previewPart.id].alt} referrerPolicy="no-referrer"/> : <ImageIcon size={50}/>} 
            <h3>{previewPart.name}</h3>
            {previewPart.oemNumber ? <code>{previewPart.oemNumber}</code> : null}
            {previewPart.source.url ? <a href={previewPart.source.url} target="_blank" rel="noreferrer">Open verified catalog source <ExternalLink size={12}/></a> : null}
          </div>
        </div>
      ) : null}
    </main>
  );
}
