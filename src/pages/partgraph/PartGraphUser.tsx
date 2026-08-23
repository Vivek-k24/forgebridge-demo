import {useEffect, useMemo, useRef, useState} from 'react';
import {
  Camera,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  ExternalLink,
  ImageOff,
  Info,
  Maximize2,
  PackageCheck,
  RotateCcw,
  Save,
  Search,
  ShieldAlert,
  ShieldCheck,
  ShoppingCart,
  Smartphone,
  Wrench,
  X,
} from 'lucide-react';
import {
  commerceSources,
  demoParts,
  demoRelations,
  initialPartStates,
  sourceLedger,
  type PartNode,
  type PartState,
} from '../../data/partGraphDemo';
import {partImageById} from '../../data/partGraphImages';
import {
  demoHondaIdentity,
  hasVerifiedDemoCoverage,
  identityTrimLabel,
  type HondaVehicleIdentity,
} from '../../lib/hondaVehicleService';
import {buildRepairLines, questionForPart} from '../../lib/repairEngine';
import {HondaVehicleSelector} from './HondaVehicleSelector';

const STORAGE_KEY = 'partgraph.v0.repair-state';
const APP_URL = 'https://vivek-k24.github.io/forgebridge-demo/#/';
const QR_URL = `https://api.qrserver.com/v1/create-qr-code/?size=160x160&margin=8&data=${encodeURIComponent(APP_URL)}`;

type PartFilter = 'attention' | 'all' | 'have';

const stateLabels: Record<PartState, string> = {
  need: 'Need',
  have: 'Have',
  inspect: 'Inspect',
  'not-sure': 'Not sure',
};

const stateIcons: Record<PartState, typeof CheckCircle2> = {
  need: ShoppingCart,
  have: CheckCircle2,
  inspect: CircleHelp,
  'not-sure': CircleHelp,
};

const providerDomains: Record<string, string> = {
  hondapartsnow: 'hondapartsnow.com',
  hondafactoryparts: 'hondafactoryparts.com',
  hondapartsonline: 'hondapartsonline.net',
  autopartsprime: 'autopartsprime.com',
};

function loadSavedStates(): Record<string, PartState> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return initialPartStates;
    const parsed = JSON.parse(raw) as Record<string, PartState>;
    return {...initialPartStates, ...parsed};
  } catch {
    return initialPartStates;
  }
}

function sellerUrl(part: PartNode, source: {id: string; name: string}) {
  const direct = part.purchaseLinks?.find((link) => link.name === source.name);
  if (direct) return direct.url;
  if (!part.oemNumber || part.source.status !== 'verified') return null;
  const q = encodeURIComponent(part.oemNumber);
  if (source.id === 'ebay') return `https://www.ebay.com/sch/i.html?_nkw=${q}`;
  const domain = providerDomains[source.id];
  if (!domain) return null;
  return `https://www.google.com/search?q=${encodeURIComponent(`site:${domain} "${part.oemNumber}"`)}`;
}

function PartThumbnail({part, onOpen}: {part: PartNode; onOpen: (part: PartNode) => void}) {
  const image = partImageById[part.id];

  if (!image) {
    return (
      <a className="pg-part-thumb pg-part-thumb--missing" href={part.source.url} target="_blank" rel="noreferrer" title="Open the source diagram">
        <ImageOff size={20} />
        <span>Source diagram</span>
      </a>
    );
  }

  return (
    <button className="pg-part-thumb" type="button" onClick={() => onOpen(part)} aria-label={`Enlarge photo of ${part.name}`}>
      <img src={image.url} alt={image.alt} loading="lazy" referrerPolicy="no-referrer" />
      <span className="pg-thumb-action"><Maximize2 size={13} /></span>
      <span className="pg-hover-preview" aria-hidden="true">
        <img src={image.url} alt="" loading="lazy" referrerPolicy="no-referrer" />
        <strong>{part.name}</strong>
        {part.oemNumber ? <code>{part.oemNumber}</code> : null}
      </span>
    </button>
  );
}

function Diagram({states}: {states: Record<string, PartState>}) {
  const byId = useMemo(() => new Map(demoParts.map((part) => [part.id, part])), []);

  return (
    <div className="pg-diagram-wrap" aria-label="Exploded assembly relationship view">
      <svg viewBox="0 0 820 550" className="pg-diagram" role="img" aria-label="Parts around the radiator assembly">
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 z" className="pg-arrow" />
          </marker>
        </defs>
        {demoRelations.map((relation, index) => {
          const from = byId.get(relation.from);
          const to = byId.get(relation.to);
          if (!from || !to) return null;
          const x1 = from.diagram.x + from.diagram.w / 2;
          const y1 = from.diagram.y + from.diagram.h / 2;
          const x2 = to.diagram.x + to.diagram.w / 2;
          const y2 = to.diagram.y + to.diagram.h / 2;
          return (
            <line
              key={`${relation.from}-${relation.to}-${index}`}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              className={relation.source.status === 'verified' ? 'pg-edge pg-edge--verified' : 'pg-edge pg-edge--prototype'}
              markerEnd="url(#arrow)"
            />
          );
        })}
        {demoParts.map((part) => {
          const state = states[part.id] ?? 'not-sure';
          return (
            <g key={part.id} className={`pg-node pg-node--${state}`}>
              <rect x={part.diagram.x} y={part.diagram.y} width={part.diagram.w} height={part.diagram.h} rx="16" />
              <text x={part.diagram.x + part.diagram.w / 2} y={part.diagram.y + part.diagram.h / 2 - 5} textAnchor="middle">
                {part.name.length > 24 ? `${part.name.slice(0, 23)}…` : part.name}
              </text>
              <text className="pg-node-state" x={part.diagram.x + part.diagram.w / 2} y={part.diagram.y + part.diagram.h / 2 + 18} textAnchor="middle">
                {stateLabels[state]}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="pg-diagram-legend">
        <span><i className="need" />Need</span>
        <span><i className="have" />Have</span>
        <span><i className="inspect" />Inspect</span>
        <span><i className="not-sure" />Not sure</span>
      </div>
      <p className="pg-diagram-note">This view shows verified part relationships and relative assembly logic. It is not dimensional CAD.</p>
    </div>
  );
}

export function PartGraphUser() {
  const [states, setStates] = useState<Record<string, PartState>>(loadSavedStates);
  const [vehicle, setVehicle] = useState<HondaVehicleIdentity>(demoHondaIdentity);
  const [targetPartId, setTargetPartId] = useState('radiator');
  const [photoName, setPhotoName] = useState('');
  const [photoUrl, setPhotoUrl] = useState('');
  const [savedAt, setSavedAt] = useState('');
  const [filter, setFilter] = useState<PartFilter>('attention');
  const [previewPartId, setPreviewPartId] = useState<string | null>(null);

  const vehicleRef = useRef<HTMLDivElement>(null);
  const scopeRef = useRef<HTMLElement>(null);
  const cameraRef = useRef<HTMLElement>(null);
  const assemblyRef = useRef<HTMLElement>(null);
  const packetRef = useRef<HTMLElement>(null);
  const diagramRef = useRef<HTMLElement>(null);

  const coverageSupported = hasVerifiedDemoCoverage(vehicle);
  const targetPart = demoParts.find((part) => part.id === targetPartId) ?? demoParts[0];
  const lines = useMemo(() => buildRepairLines(demoParts, states), [states]);
  const needed = lines.filter((line) => line.state === 'need');
  const unresolved = lines.filter((line) => line.state === 'not-sure');
  const inspect = lines.filter((line) => line.state === 'inspect');
  const have = lines.filter((line) => line.state === 'have');
  const previewPart = previewPartId ? demoParts.find((part) => part.id === previewPartId) ?? null : null;
  const previewImage = previewPart ? partImageById[previewPart.id] : null;

  const visibleParts = useMemo(() => {
    const filtered = filter === 'all'
      ? demoParts
      : filter === 'have'
        ? demoParts.filter((part) => states[part.id] === 'have')
        : demoParts.filter((part) => states[part.id] !== 'have');

    return [...filtered].sort((a, b) => {
      if (a.id === targetPartId) return -1;
      if (b.id === targetPartId) return 1;
      return 0;
    });
  }, [filter, states, targetPartId]);

  useEffect(() => () => {
    if (photoUrl) URL.revokeObjectURL(photoUrl);
  }, [photoUrl]);

  useEffect(() => {
    if (!previewPartId) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setPreviewPartId(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [previewPartId]);

  const changeState = (id: string, state: PartState) => {
    setStates((current) => ({...current, [id]: state}));
  };

  const saveRepair = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(states));
    setSavedAt(new Date().toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'}));
  };

  const resetRepair = () => {
    setStates(initialPartStates);
    localStorage.removeItem(STORAGE_KEY);
    setSavedAt('');
    setFilter('attention');
  };

  const useVerifiedDemo = () => {
    setVehicle(demoHondaIdentity);
    setTargetPartId('radiator');
    window.setTimeout(() => scopeRef.current?.scrollIntoView({behavior: 'smooth', block: 'start'}), 0);
  };

  const onPhoto = (file?: File) => {
    if (!file) return;
    if (photoUrl) URL.revokeObjectURL(photoUrl);
    setPhotoName(file.name);
    setPhotoUrl(URL.createObjectURL(file));
  };

  const scrollTo = (ref: {current: HTMLElement | null}) => ref.current?.scrollIntoView({behavior: 'smooth', block: 'start'});
  const vehicleTrim = identityTrimLabel(vehicle);

  return (
    <main className="pg-shell">
      <header className="pg-header">
        <a className="pg-brand" href="#/" aria-label="PartGraph home">
          <span className="pg-mark"><Wrench size={19} /></span>
          <span><strong>PARTGRAPH</strong><small>Complete repair parts</small></span>
        </a>
        <nav className="pg-jump-nav" aria-label="Page sections">
          <button type="button" onClick={() => scrollTo(vehicleRef)}>Vehicle</button>
          <button type="button" onClick={() => scrollTo(scopeRef)}>Repair</button>
          <button type="button" onClick={() => scrollTo(cameraRef)}>Photo</button>
          <button type="button" onClick={() => scrollTo(assemblyRef)}>Parts</button>
          <button type="button" onClick={() => scrollTo(packetRef)}>Buy</button>
        </nav>
        <button type="button" className="pg-save" onClick={saveRepair}><Save size={15} />{savedAt ? `Saved ${savedAt}` : 'Save repair'}</button>
      </header>

      <section className="pg-hero">
        <div className="pg-hero-copy">
          <span className="pg-kicker">HONDA REPAIR BUILDER</span>
          <h1>Get every part before you start the repair.</h1>
          <p>Identify the exact Honda, choose the repair area, mark what you already have, and PartGraph builds the complete assembly list—not just the big part.</p>
          <div className="pg-hero-trust">
            <span><ShieldCheck size={15} /> Source-backed identity</span>
            <span><CheckCircle2 size={15} /> No account needed</span>
            <span><Smartphone size={15} /> Built for phone photos</span>
          </div>
        </div>
        <aside className="pg-qr-card" aria-label="Open PartGraph on a phone">
          <img src={QR_URL} alt="QR code to open PartGraph on a phone" />
          <div><strong>Open on your phone</strong><span>Scan, then take photos beside the car.</span></div>
        </aside>
      </section>

      <div ref={vehicleRef} className="pg-vehicle-anchor">
        <HondaVehicleSelector value={vehicle} onChange={(identity) => { setVehicle(identity); setPreviewPartId(null); }} />
      </div>

      <section className="pg-scope-builder" ref={scopeRef}>
        <div className="pg-scope-heading">
          <div>
            <span className="pg-eyebrow">STEP 2 · CHOOSE THE REPAIR</span>
            <h2>Where are you working?</h2>
            <p>Block → sub-block → target part. The target moves to the top of the assembly check, while connected pieces stay visible.</p>
          </div>
          <span className={`pg-coverage-pill ${coverageSupported ? 'ready' : 'blocked'}`}>
            {coverageSupported ? <ShieldCheck size={14} /> : <ShieldAlert size={14} />}
            {coverageSupported ? 'Verified graph available' : 'Vehicle identified · graph not published'}
          </span>
        </div>

        <div className="pg-scope-grid">
          <label className="pg-field">
            <span>Block</span>
            <select value="cooling" disabled={!coverageSupported}>
              <option value="cooling">Cooling</option>
              <option disabled>Air conditioning — next</option>
              <option disabled>Front body — planned</option>
              <option disabled>Engine — planned</option>
              <option disabled>Brakes — planned</option>
              <option disabled>Suspension — planned</option>
              <option disabled>Electrical — planned</option>
            </select>
          </label>
          <label className="pg-field">
            <span>Sub-block</span>
            <select value="front-cooling" disabled={!coverageSupported}>
              <option value="front-cooling">Front cooling / radiator area</option>
            </select>
          </label>
          <label className="pg-field pg-field--target">
            <span>Target part</span>
            <select value={targetPartId} onChange={(event) => setTargetPartId(event.target.value)} disabled={!coverageSupported}>
              {demoParts.map((part) => <option key={part.id} value={part.id}>{part.name}</option>)}
            </select>
          </label>
        </div>

        {coverageSupported ? (
          <div className="pg-scope-ready"><CheckCircle2 size={15} /> Exact published MVP coverage: 2009 Honda Civic Hybrid · US market · front cooling/radiator area.</div>
        ) : (
          <div className="pg-scope-blocked">
            <ShieldAlert size={18} />
            <div>
              <strong>We identified the Honda, but we will not reuse another car's parts graph.</strong>
              <span>Vehicle discovery is broad; verified mechanical coverage is intentionally narrow. This is the precision gate that prevents a wrong-model checklist.</span>
            </div>
            <button type="button" onClick={useVerifiedDemo}>Open the verified 2009 Civic Hybrid repair</button>
          </div>
        )}
      </section>

      <section className="pg-path" aria-label="Current repair path">
        <div><small>Make</small><strong>{vehicle.make}</strong></div>
        <span>›</span>
        <div><small>Year / model</small><strong>{vehicle.year} {vehicle.model}</strong></div>
        <span>›</span>
        <div><small>Trim / series</small><strong>{vehicleTrim}</strong></div>
        <span>›</span>
        <div><small>Block</small><strong>{coverageSupported ? 'Cooling' : '—'}</strong></div>
        <span>›</span>
        <div><small>Sub-block</small><strong>{coverageSupported ? 'Front cooling' : '—'}</strong></div>
        <span>›</span>
        <div className="active"><small>Part</small><strong>{coverageSupported ? targetPart.name : 'Waiting for coverage'}</strong></div>
      </section>

      {coverageSupported ? (
        <>
          <section className="pg-camera-prompt" ref={cameraRef}>
            <div className="pg-camera-icon"><Camera size={25} /></div>
            <div className="pg-camera-copy">
              <span className="pg-eyebrow">PHOTO HELP</span>
              <h2>If you’re not sure what the parts are called, let us take a look.</h2>
              <p>Take a clear photo with your phone. For now, we pin your photo while you compare it with verified part photos in the checklist; automatic matching will be added only when it can fail safely.</p>
            </div>
            {photoUrl ? (
              <div className="pg-camera-result">
                <img src={photoUrl} alt="Your selected part" />
                <div><strong>{photoName}</strong><span>Stays on this device</span></div>
                <label className="pg-camera-button secondary">Retake<input type="file" accept="image/*" capture="environment" onChange={(event) => onPhoto(event.target.files?.[0])} /></label>
              </div>
            ) : (
              <label className="pg-camera-button"><Camera size={17} /> Take or choose a photo<input type="file" accept="image/*" capture="environment" onChange={(event) => onPhoto(event.target.files?.[0])} /></label>
            )}
          </section>

          <section className="pg-assembly" ref={assemblyRef}>
            <div className="pg-section-heading">
              <div>
                <span className="pg-eyebrow">STEP 3 · ASSEMBLY CHECK</span>
                <h2>What do you still need?</h2>
                <p><strong>{targetPart.name}</strong> is first. Tap a part photo to enlarge it; on a computer, hover over the thumbnail for a quick preview.</p>
              </div>
              <div className="pg-progress-summary">
                <strong>{unresolved.length}</strong>
                <span>still unanswered</span>
              </div>
            </div>

            {photoUrl ? <div className="pg-pinned-photo"><img src={photoUrl} alt="Your part for comparison" /><span>Your photo stays visible while you compare.</span></div> : null}

            <div className="pg-filter-row" role="group" aria-label="Filter assembly parts">
              <button type="button" className={filter === 'attention' ? 'active' : ''} onClick={() => setFilter('attention')}>Needs attention <b>{demoParts.length - have.length}</b></button>
              <button type="button" className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>All parts <b>{demoParts.length}</b></button>
              <button type="button" className={filter === 'have' ? 'active' : ''} onClick={() => setFilter('have')}>Already have <b>{have.length}</b></button>
            </div>

            <div className="pg-part-grid">
              {visibleParts.map((part) => {
                const state = states[part.id] ?? 'not-sure';
                const Icon = stateIcons[state];
                return (
                  <article key={part.id} className={`pg-part-card pg-part-card--${state} ${part.id === targetPartId ? 'pg-part-card--target' : ''}`}>
                    <PartThumbnail part={part} onOpen={(selected) => setPreviewPartId(selected.id)} />
                    <div className="pg-part-main">
                      <div className="pg-part-topline">
                        {part.id === targetPartId ? <span className="pg-target-badge">Target</span> : null}
                        <span className={`pg-state-badge pg-state-badge--${state}`}><Icon size={13} />{stateLabels[state]}</span>
                        {part.source.status === 'verified' ? <span className="pg-verified"><ShieldCheck size={12} />Verified</span> : <span className="pg-service-item">Service item</span>}
                        {part.oemNumber ? <code>{part.oemNumber}</code> : null}
                      </div>
                      <h3>{part.name}{part.quantity > 1 ? ` ×${part.quantity}` : ''}</h3>
                      <p>{questionForPart(part)}</p>
                      <small>{part.description}</small>
                    </div>
                    <div className="pg-choice-group" aria-label={`State for ${part.name}`}>
                      {(['need', 'have', 'inspect', 'not-sure'] as PartState[]).map((option) => (
                        <button key={option} type="button" className={state === option ? 'active' : ''} onClick={() => changeState(part.id, option)}>
                          {stateLabels[option]}
                        </button>
                      ))}
                    </div>
                  </article>
                );
              })}
            </div>

            <div className="pg-assembly-actions">
              <div><strong>{needed.length} to buy</strong><span>{inspect.length} to inspect · {unresolved.length} not sure</span></div>
              <button className="pg-primary" type="button" onClick={() => scrollTo(packetRef)}>Review parts to buy <ChevronDown size={18} /></button>
              <button className="pg-text-button" type="button" onClick={resetRepair}><RotateCcw size={14} /> Reset</button>
            </div>
          </section>

          <section className="pg-packet" ref={packetRef}>
            <div className="pg-section-heading">
              <div>
                <span className="pg-eyebrow">YOUR REPAIR LIST</span>
                <h2>{needed.length ? `${needed.length} items to find` : 'Nothing marked for purchase yet'}</h2>
                <p>Each shopping path starts from the verified OEM identity. Store “fits your vehicle” badges never override the part record.</p>
              </div>
              <span className="pg-package-status"><PackageCheck size={18} /> {vehicle.year} {vehicle.model} {vehicleTrim}</span>
            </div>

            <div className="pg-buy-list">
              {needed.map(({part}) => (
                <article className="pg-buy-card" key={part.id}>
                  <PartThumbnail part={part} onOpen={(selected) => setPreviewPartId(selected.id)} />
                  <div className="pg-buy-info">
                    <div><strong>{part.name}</strong><span>Qty {part.quantity}</span></div>
                    <code>{part.oemNumber ?? 'Service specification not loaded'}</code>
                    <small>{part.source.status === 'verified' ? 'OEM identity checked against the current vehicle catalog.' : 'Purchase details wait for an authoritative service source.'}</small>
                  </div>
                  <div className="pg-sellers" aria-label={`Purchase links for ${part.name}`}>
                    {commerceSources.map((source) => {
                      const url = sellerUrl(part, source);
                      const direct = part.purchaseLinks?.some((link) => link.name === source.name);
                      return url ? (
                        <a key={source.id} href={url} target="_blank" rel="noreferrer" title={direct ? 'Direct researched product page' : `Search exact OEM number ${part.oemNumber}`}>
                          <ExternalLink size={13} /><span>{source.name}</span><small>{direct ? 'direct' : 'OEM search'}</small>
                        </a>
                      ) : (
                        <span key={source.id} className="disabled"><Search size={13} /><span>{source.name}</span></span>
                      );
                    })}
                  </div>
                </article>
              ))}
            </div>

            <div className="pg-service-status">
              <Info size={19} />
              <div>
                <strong>Repair instructions follow the same precision rule.</strong>
                <span>Torque, coolant quantity, drain/refill steps, bleed procedure and safety-critical service instructions stay hidden until the exact Honda service source for this configuration is loaded and verified.</span>
              </div>
            </div>
          </section>

          <section className="pg-exploded" ref={diagramRef}>
            <div className="pg-section-heading compact">
              <div>
                <span className="pg-eyebrow">ASSEMBLY VIEW</span>
                <h2>See how the selected pieces relate.</h2>
                <p>The same relationship data that builds the checklist drives this view.</p>
              </div>
            </div>
            <Diagram states={states} />
          </section>

          <section className="pg-proof">
            <details>
              <summary><ShieldCheck size={17} /> How PartGraph verifies this repair</summary>
              <div className="pg-proof-body">
                <p>Mechanical claims are stored with a source trail. Shopping searches happen only after the OEM identity is established.</p>
                <div className="pg-proof-links">
                  {sourceLedger.map((source) => (
                    <a key={source.id} href={source.url} target="_blank" rel="noreferrer"><span><strong>{source.label}</strong><small>{source.scope}</small></span><ExternalLink size={14} /></a>
                  ))}
                </div>
              </div>
            </details>
          </section>
        </>
      ) : (
        <section className="pg-coverage-stop" ref={cameraRef}>
          <ShieldAlert size={28} />
          <div>
            <span className="pg-eyebrow">MECHANICAL DATA GATE</span>
            <h2>No guessed repair data.</h2>
            <p>PartGraph can identify this Honda, but the verified assembly graph for this exact configuration has not been published yet. We stop here instead of showing parts from a different trim, engine, body or production split.</p>
          </div>
          <button type="button" onClick={useVerifiedDemo}>Show the current verified repair</button>
        </section>
      )}

      <footer className="pg-footer">
        <strong>PartGraph</strong>
        <span>{coverageSupported ? 'Published mechanical coverage: 2009 Honda Civic Hybrid · US market · front cooling/radiator area.' : `Vehicle identification loaded for ${vehicle.year} Honda ${vehicle.model}; mechanical coverage is not published for this selection.`}</span>
      </footer>

      {coverageSupported ? (
        <div className="pg-mobile-bar">
          <div><strong>{needed.length} to buy</strong><span>{unresolved.length} unanswered</span></div>
          <button type="button" onClick={() => scrollTo(packetRef)}>Review list</button>
        </div>
      ) : null}

      {previewPart && previewImage ? (
        <div className="pg-image-modal" role="dialog" aria-modal="true" aria-label={`Photo of ${previewPart.name}`} onClick={() => setPreviewPartId(null)}>
          <div className="pg-image-modal-card" onClick={(event) => event.stopPropagation()}>
            <button type="button" className="pg-modal-close" onClick={() => setPreviewPartId(null)} aria-label="Close image"><X size={19} /></button>
            <img src={previewImage.url} alt={previewImage.alt} referrerPolicy="no-referrer" />
            <div><strong>{previewPart.name}</strong>{previewPart.oemNumber ? <code>{previewPart.oemNumber}</code> : null}</div>
            <a href={previewImage.sourcePageUrl} target="_blank" rel="noreferrer">Open image source <ExternalLink size={13} /></a>
          </div>
        </div>
      ) : null}
    </main>
  );
}
