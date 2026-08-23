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
import {commerceSources, type PartNode, type PartRelation, type PartState} from '../../data/partGraphDemo';
import {partImageById} from '../../data/partGraphImages';
import {
  getRepairBlock,
  getRepairGraph,
  initialStatesForGraph,
  publishedRepairGraphs,
  repairBlocks,
  type RepairBlockId,
  type RepairGraphDefinition,
} from '../../data/partGraphSystems';
import {
  demoHondaIdentity,
  hasVerifiedDemoCoverage,
  identityTrimLabel,
  is2009CivicCandidate,
  type HondaVehicleIdentity,
} from '../../lib/hondaVehicleService';
import {buildRepairLines, questionForPart} from '../../lib/repairEngine';
import {HondaVehicleSelector} from './HondaVehicleSelector';

const LEGACY_STORAGE_KEY = 'partgraph.v0.repair-state';
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

function storageKey(graphId: string) {
  return `partgraph.v1.repair-state.${graphId}`;
}

function loadSavedStates(graph: RepairGraphDefinition): Record<string, PartState> {
  const fallback = initialStatesForGraph(graph);
  try {
    const raw = localStorage.getItem(storageKey(graph.id)) || (graph.id === 'front-cooling' ? localStorage.getItem(LEGACY_STORAGE_KEY) : null);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as Record<string, PartState>;
    const validIds = new Set(graph.parts.map((part) => part.id));
    return Object.fromEntries(
      Object.entries({...fallback, ...parsed}).filter(([id]) => validIds.has(id)),
    );
  } catch {
    return fallback;
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
    if (part.source.url) {
      return (
        <a className="pg-part-thumb pg-part-thumb--missing" href={part.source.url} target="_blank" rel="noreferrer" title="Open the source diagram">
          <ImageOff size={20} />
          <span>Source diagram</span>
        </a>
      );
    }
    return (
      <span className="pg-part-thumb pg-part-thumb--missing" title="No verified preview image yet">
        <ImageOff size={20} />
        <span>No verified image</span>
      </span>
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

function Diagram({parts, relations, states}: {parts: PartNode[]; relations: PartRelation[]; states: Record<string, PartState>}) {
  const byId = useMemo(() => new Map(parts.map((part) => [part.id, part])), [parts]);

  return (
    <div className="pg-diagram-wrap" aria-label="Exploded assembly relationship view">
      <svg viewBox="0 0 820 550" className="pg-diagram" role="img" aria-label="Parts in the selected assembly">
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 z" className="pg-arrow" />
          </marker>
        </defs>
        {relations.map((relation, index) => {
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
        {parts.map((part) => {
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
      <p className="pg-diagram-note">Logical relationship view from the selected catalog graph. It is not dimensional CAD and does not imply service order.</p>
    </div>
  );
}

export function PartGraphUser() {
  const initialGraph = getRepairGraph('front-cooling');
  const [vehicle, setVehicle] = useState<HondaVehicleIdentity>(demoHondaIdentity);
  const [coverageOverride, setCoverageOverride] = useState(false);
  const [blockId, setBlockId] = useState<RepairBlockId>('cooling');
  const [graphId, setGraphId] = useState(initialGraph.id);
  const [targetPartId, setTargetPartId] = useState(initialGraph.defaultTargetPartId);
  const [states, setStates] = useState<Record<string, PartState>>(() => loadSavedStates(initialGraph));
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

  const activeBlock = getRepairBlock(blockId);
  const activeGraph = getRepairGraph(graphId);
  const parts = activeGraph.parts;
  const relations = activeGraph.relations;
  const coverageSupported = hasVerifiedDemoCoverage(vehicle) || coverageOverride;
  const coverageCandidate = is2009CivicCandidate(vehicle) && !hasVerifiedDemoCoverage(vehicle);
  const targetPart = parts.find((part) => part.id === targetPartId) ?? parts[0];
  const lines = useMemo(() => buildRepairLines(parts, states), [parts, states]);
  const needed = lines.filter((line) => line.state === 'need');
  const unresolved = lines.filter((line) => line.state === 'not-sure');
  const inspect = lines.filter((line) => line.state === 'inspect');
  const have = lines.filter((line) => line.state === 'have');
  const previewPart = previewPartId ? parts.find((part) => part.id === previewPartId) ?? null : null;
  const previewImage = previewPart ? partImageById[previewPart.id] : null;

  const visibleParts = useMemo(() => {
    const filtered = filter === 'all'
      ? parts
      : filter === 'have'
        ? parts.filter((part) => states[part.id] === 'have')
        : parts.filter((part) => states[part.id] !== 'have');

    return [...filtered].sort((a, b) => {
      if (a.id === targetPartId) return -1;
      if (b.id === targetPartId) return 1;
      return 0;
    });
  }, [filter, parts, states, targetPartId]);

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

  const activateGraph = (graph: RepairGraphDefinition) => {
    setGraphId(graph.id);
    setBlockId(graph.blockId);
    setTargetPartId(graph.defaultTargetPartId);
    setStates(loadSavedStates(graph));
    setFilter('attention');
    setSavedAt('');
    setPreviewPartId(null);
  };

  const selectBlock = (nextBlockId: RepairBlockId) => {
    const nextBlock = getRepairBlock(nextBlockId);
    const nextGraph = nextBlock.graphs[0];
    if (!nextGraph) return;
    activateGraph(nextGraph);
  };

  const changeState = (id: string, state: PartState) => {
    setStates((current) => ({...current, [id]: state}));
  };

  const saveRepair = () => {
    localStorage.setItem(storageKey(activeGraph.id), JSON.stringify(states));
    setSavedAt(new Date().toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'}));
  };

  const resetRepair = () => {
    const reset = initialStatesForGraph(activeGraph);
    setStates(reset);
    localStorage.removeItem(storageKey(activeGraph.id));
    if (activeGraph.id === 'front-cooling') localStorage.removeItem(LEGACY_STORAGE_KEY);
    setSavedAt('');
    setFilter('attention');
  };

  const useVerifiedDemo = () => {
    setVehicle(demoHondaIdentity);
    setCoverageOverride(false);
    activateGraph(getRepairGraph('front-cooling'));
    window.setTimeout(() => scopeRef.current?.scrollIntoView({behavior: 'smooth', block: 'start'}), 0);
  };

  const confirmHybridCoverage = () => {
    setCoverageOverride(true);
    activateGraph(getRepairGraph('front-cooling'));
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
        <button type="button" className="pg-save" onClick={saveRepair} disabled={!coverageSupported}><Save size={15} />{savedAt ? `Saved ${savedAt}` : 'Save repair'}</button>
      </header>

      <section className="pg-hero">
        <div className="pg-hero-copy">
          <span className="pg-kicker">HONDA REPAIR BUILDER</span>
          <h1>Get every part before you start the repair.</h1>
          <p>Identify the exact Honda, choose the repair area, mark what you already have, and PartGraph builds the connected assembly list—not just the big part.</p>
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
        <HondaVehicleSelector
          value={vehicle}
          onChange={(identity) => {
            setVehicle(identity);
            setCoverageOverride(false);
            setPreviewPartId(null);
          }}
        />
      </div>

      <section className="pg-scope-builder" ref={scopeRef}>
        <div className="pg-scope-heading">
          <div>
            <span className="pg-eyebrow">STEP 2 · CHOOSE THE REPAIR</span>
            <h2>Where are you working?</h2>
            <p>Block → sub-block → target part. Only source-backed graphs are selectable.</p>
          </div>
          <span className={`pg-coverage-pill ${coverageSupported ? 'ready' : 'blocked'}`}>
            {coverageSupported ? <ShieldCheck size={14} /> : <ShieldAlert size={14} />}
            {coverageSupported ? `Published graph · ${repairBlocks.length} systems / ${publishedRepairGraphs.length} assemblies` : 'Vehicle identified · graph not matched'}
          </span>
        </div>

        <div className="pg-scope-grid">
          <label className="pg-field">
            <span>Block</span>
            <select value={blockId} disabled={!coverageSupported} onChange={(event) => selectBlock(event.target.value as RepairBlockId)}>
              {repairBlocks.map((block) => <option key={block.id} value={block.id}>{block.label}</option>)}
              <option disabled>Cosmetics / body — later</option>
              <option disabled>Lighting — later</option>
              <option disabled>Interior / media — later</option>
              <option disabled>Suspension / general chassis — later</option>
            </select>
          </label>
          <label className="pg-field">
            <span>Sub-block</span>
            <select
              value={activeGraph.id}
              disabled={!coverageSupported}
              onChange={(event) => activateGraph(getRepairGraph(event.target.value))}
            >
              {activeBlock.graphs.map((graph) => <option key={graph.id} value={graph.id}>{graph.label}</option>)}
            </select>
          </label>
          <label className="pg-field pg-field--target">
            <span>Target part</span>
            <select value={targetPartId} onChange={(event) => setTargetPartId(event.target.value)} disabled={!coverageSupported}>
              {parts.map((part) => <option key={part.id} value={part.id}>{part.name}</option>)}
            </select>
          </label>
        </div>

        {coverageSupported ? (
          <div className="pg-scope-ready">
            <CheckCircle2 size={15} />
            Published catalog coverage: 2009 Honda Civic Hybrid · US market · Cooling, A/C, Drivetrain and Safety. {coverageOverride ? 'Vehicle variant was confirmed by the user.' : 'Hybrid identity matched from vehicle data.'}
          </div>
        ) : (
          <div className="pg-scope-blocked">
            <ShieldAlert size={18} />
            <div>
              <strong>We identified the Honda, but we will not reuse another car's parts graph.</strong>
              <span>Published mechanical coverage is currently the 2009 US Civic Hybrid catalog. We stop instead of guessing across trim, engine or production differences.</span>
            </div>
            {coverageCandidate ? <button type="button" onClick={confirmHybridCoverage}>This is a 2009 Civic Hybrid — use its catalog graph</button> : <button type="button" onClick={useVerifiedDemo}>Open the verified 2009 Civic Hybrid repair</button>}
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
        <div><small>Block</small><strong>{coverageSupported ? activeBlock.label : '—'}</strong></div>
        <span>›</span>
        <div><small>Sub-block</small><strong>{coverageSupported ? activeGraph.shortLabel : '—'}</strong></div>
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
              <p>Take a clear photo with your phone. For now, we pin your photo while you compare it with verified part photos or the source diagram; automatic matching will be added only when it can fail safely.</p>
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

          {activeGraph.warning ? (
            <div className="pg-service-status" style={{maxWidth: 1192, margin: '0 auto 12px'}}>
              <ShieldAlert size={19} />
              <div><strong>Safety / precision boundary</strong><span>{activeGraph.warning}</span></div>
            </div>
          ) : null}

          <section className="pg-assembly" ref={assemblyRef}>
            <div className="pg-section-heading">
              <div>
                <span className="pg-eyebrow">STEP 3 · ASSEMBLY CHECK</span>
                <h2>What do you still need?</h2>
                <p><strong>{targetPart.name}</strong> is first. Tap a verified part photo to enlarge it; items without a licensed preview link to the exact source diagram.</p>
              </div>
              <div className="pg-progress-summary"><strong>{unresolved.length}</strong><span>still unanswered</span></div>
            </div>

            {photoUrl ? <div className="pg-pinned-photo"><img src={photoUrl} alt="Your part for comparison" /><span>Your photo stays visible while you compare.</span></div> : null}

            <div className="pg-filter-row" role="group" aria-label="Filter assembly parts">
              <button type="button" className={filter === 'attention' ? 'active' : ''} onClick={() => setFilter('attention')}>Needs attention <b>{parts.length - have.length}</b></button>
              <button type="button" className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>All parts <b>{parts.length}</b></button>
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
                        <button key={option} type="button" className={state === option ? 'active' : ''} onClick={() => changeState(part.id, option)}>{stateLabels[option]}</button>
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
                <p>Each shopping path starts from a catalog OEM identity. Store “fits your vehicle” badges never override the graph.</p>
              </div>
              <span className="pg-package-status"><PackageCheck size={18} /> {activeGraph.shortLabel} · {vehicle.year} {vehicle.model}</span>
            </div>

            <div className="pg-buy-list">
              {needed.map(({part}) => (
                <article className="pg-buy-card" key={part.id}>
                  <PartThumbnail part={part} onOpen={(selected) => setPreviewPartId(selected.id)} />
                  <div className="pg-buy-info">
                    <div><strong>{part.name}</strong><span>Qty {part.quantity}</span></div>
                    <code>{part.oemNumber ?? 'Service specification not loaded'}</code>
                    <small>{part.source.status === 'verified' ? 'OEM identity checked against the selected exact-configuration catalog.' : 'Purchase details wait for an authoritative source.'}</small>
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
                <strong>Catalog graph ≠ service manual.</strong>
                <span>Torque, fluid quantities, bleeding, calibration, refrigerant procedures and safety-critical sequence stay hidden unless an exact authoritative service source is loaded and verified.</span>
              </div>
            </div>
          </section>

          <section className="pg-exploded">
            <div className="pg-section-heading compact">
              <div><span className="pg-eyebrow">ASSEMBLY VIEW</span><h2>See how the selected pieces relate.</h2><p>The same relationship data that builds the checklist drives this logical view.</p></div>
            </div>
            <Diagram parts={parts} relations={relations} states={states} />
          </section>

          <section className="pg-proof">
            <details>
              <summary><ShieldCheck size={17} /> How PartGraph verifies this repair</summary>
              <div className="pg-proof-body">
                <p>Mechanical claims are stored with a source trail. Shopping searches happen only after the OEM identity is established.</p>
                <div className="pg-proof-links">
                  {activeGraph.sources.map((source) => (
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
            <p>PartGraph can identify this Honda, but the published graph currently covers the 2009 US Civic Hybrid. We stop instead of showing parts from a different trim, engine, body or production split.</p>
          </div>
          {coverageCandidate ? <button type="button" onClick={confirmHybridCoverage}>Confirm this is a 2009 Civic Hybrid</button> : <button type="button" onClick={useVerifiedDemo}>Show the current published vehicle</button>}
        </section>
      )}

      <footer className="pg-footer">
        <strong>PartGraph</strong>
        <span>{coverageSupported ? `Published coverage: 2009 Honda Civic Hybrid · Cooling, A/C, Drivetrain and Safety · ${publishedRepairGraphs.length} assembly graphs.` : `Vehicle identification loaded for ${vehicle.year} Honda ${vehicle.model}; published mechanical coverage did not match.`}</span>
      </footer>

      {coverageSupported ? (
        <div className="pg-mobile-bar"><div><strong>{needed.length} to buy</strong><span>{unresolved.length} unanswered</span></div><button type="button" onClick={() => scrollTo(packetRef)}>Review list</button></div>
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
