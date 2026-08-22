import {useEffect, useMemo, useRef, useState} from 'react';
import {
  Camera,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  Database,
  ExternalLink,
  Gauge,
  PackageCheck,
  RotateCcw,
  Save,
  Search,
  ShieldCheck,
  ShoppingCart,
  Wrench,
  XCircle,
} from 'lucide-react';
import {
  commerceSources,
  demoParts,
  demoRelations,
  demoVehicle,
  initialPartStates,
  sourceLedger,
  type PartNode,
  type PartState,
} from '../../data/partGraphDemo';
import {buildRepairLines, completenessScore, questionForPart, validateGraph} from '../../lib/repairEngine';

const STORAGE_KEY = 'partgraph.v0.repair-state';

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

function statusClass(state: PartState) {
  return `pg-state pg-state--${state}`;
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

function Diagram({states}: {states: Record<string, PartState>}) {
  const byId = useMemo(() => new Map(demoParts.map((part) => [part.id, part])), []);
  return (
    <div className="pg-diagram-wrap" aria-label="Logical exploded assembly diagram">
      <svg viewBox="0 0 820 550" className="pg-diagram" role="img" aria-label="Logical relationships around the radiator repair target">
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
          return <line key={`${relation.from}-${relation.to}-${index}`} x1={x1} y1={y1} x2={x2} y2={y2} className={relation.source.status === 'verified' ? 'pg-edge pg-edge--verified' : 'pg-edge pg-edge--prototype'} markerEnd="url(#arrow)" />;
        })}
        {demoParts.map((part) => {
          const state = states[part.id] ?? 'not-sure';
          return (
            <g key={part.id} className={`pg-node pg-node--${state}`}>
              <rect x={part.diagram.x} y={part.diagram.y} width={part.diagram.w} height={part.diagram.h} rx="16" />
              <text x={part.diagram.x + part.diagram.w / 2} y={part.diagram.y + part.diagram.h / 2 - 5} textAnchor="middle">
                {part.name.length > 24 ? part.name.slice(0, 23) + '…' : part.name}
              </text>
              <text className="pg-node-state" x={part.diagram.x + part.diagram.w / 2} y={part.diagram.y + part.diagram.h / 2 + 18} textAnchor="middle">
                {stateLabels[state]}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="pg-diagram-note">
        Solid lines = catalog-backed relationship. Dashed lines = prototype inference/recommendation. Diagram is logical, not dimensional CAD.
      </div>
    </div>
  );
}

export function PartGraphPrototype() {
  const [states, setStates] = useState<Record<string, PartState>>(loadSavedStates);
  const [photoName, setPhotoName] = useState<string>('');
  const [photoUrl, setPhotoUrl] = useState<string>('');
  const [savedAt, setSavedAt] = useState<string>('');
  const packetRef = useRef<HTMLDivElement>(null);

  const lines = useMemo(() => buildRepairLines(demoParts, states), [states]);
  const score = useMemo(() => completenessScore(lines), [lines]);
  const graphErrors = useMemo(() => validateGraph(demoParts, demoRelations), []);
  const needed = lines.filter((line) => line.state === 'need');
  const unresolved = lines.filter((line) => line.state === 'not-sure');
  const inspect = lines.filter((line) => line.state === 'inspect');
  const verifiedParts = demoParts.filter((part) => part.source.status === 'verified').length;
  const verifiedRelations = demoRelations.filter((relation) => relation.source.status === 'verified').length;

  useEffect(() => () => {
    if (photoUrl) URL.revokeObjectURL(photoUrl);
  }, [photoUrl]);

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
  };

  const onPhoto = (file?: File) => {
    if (!file) return;
    if (photoUrl) URL.revokeObjectURL(photoUrl);
    setPhotoName(file.name);
    setPhotoUrl(URL.createObjectURL(file));
  };

  return (
    <main className="pg-shell">
      <header className="pg-header">
        <div className="pg-brand">
          <div className="pg-mark"><Wrench size={20} /></div>
          <div>
            <strong>PARTGRAPH</strong>
            <span>Honda-first repair intelligence</span>
          </div>
        </div>
        <div className="pg-header-badges">
          <span><Database size={15} /> deterministic graph</span>
          <span><Gauge size={15} /> 0 runtime LLM calls</span>
          <button type="button" className="pg-header-action" onClick={saveRepair}><Save size={14} />{savedAt ? `Saved ${savedAt}` : 'Save locally'}</button>
        </div>
      </header>

      <section className="pg-hero">
        <div className="pg-kicker">COMPLETE THE REPAIR, NOT JUST THE CART</div>
        <h1>Reconstruct the whole assembly before you order.</h1>
        <p>
          This first real code slice starts with one exact vehicle configuration and one radiator-area repair. The graph determines what belongs, what connects, what should be inspected, and which OEM identity can be used for shopping.
        </p>
        <div className="pg-truth-banner">
          <ShieldCheck size={21} />
          <div>
            <strong>Precision rule</strong>
            <span>Green “verified” records below are backed by exact-configuration OEM/dealer catalog pages. Torque, coolant capacity, bleed procedure, refrigerant work and other service-manual facts remain locked until the authoritative service source is verified.</span>
          </div>
        </div>
      </section>

      <section className="pg-workflow" aria-label="Repair selection workflow">
        <div className="pg-step pg-step--done"><span>1</span><div><small>Vehicle</small><strong>{demoVehicle.year} {demoVehicle.make} {demoVehicle.model}</strong><em>{demoVehicle.trim} · {demoVehicle.engine} · {demoVehicle.transmission}</em></div></div>
        <div className="pg-step pg-step--done"><span>2</span><div><small>Block</small><strong>Cooling</strong><em>Engine cooling system</em></div></div>
        <div className="pg-step pg-step--done"><span>3</span><div><small>Sub-block</small><strong>Front cooling module</strong><em>Radiator / fan / condenser area</em></div></div>
        <div className="pg-step pg-step--active"><span>4</span><div><small>Target part</small><strong>Radiator</strong><em>OEM 19010-RRH-901</em></div></div>
      </section>

      <section className="pg-evidence-strip" aria-label="Data coverage summary">
        <div><strong>{verifiedParts}</strong><span>catalog-backed part identities</span></div>
        <div><strong>{verifiedRelations}</strong><span>catalog-backed relationships</span></div>
        <div><strong>{sourceLedger.length}</strong><span>exact-vehicle source pages</span></div>
        <div><strong>5</strong><span>purchase paths for main part</span></div>
      </section>

      <section className="pg-check-section">
        <div className="pg-section-heading">
          <div>
            <span className="pg-eyebrow">ASSEMBLY CHECK</span>
            <h2>Tell us what survived.</h2>
            <p>The questions come from typed graph records. No prompt is generated and no language model is called.</p>
          </div>
          <div className="pg-score">
            <strong>{score}%</strong>
            <span>decisions resolved</span>
          </div>
        </div>

        <div className="pg-checklist">
          {demoParts.map((part) => {
            const state = states[part.id] ?? 'not-sure';
            const Icon = stateIcons[state];
            return (
              <article key={part.id} className="pg-part-question">
                <div className="pg-part-copy">
                  <div className="pg-part-meta-row">
                    <div className={statusClass(state)}><Icon size={16} /> {stateLabels[state]}</div>
                    <span className={`pg-source-status pg-source-status--${part.source.status}`}>{part.source.status}</span>
                    {part.oemNumber ? <code>{part.oemNumber}</code> : <code>service spec locked</code>}
                  </div>
                  <h3>{part.name}{part.quantity > 1 ? ` ×${part.quantity}` : ''}</h3>
                  <p>{questionForPart(part)}</p>
                  <small>{part.description}</small>
                  {part.supersededNumbers?.length ? <small className="pg-supersession">Supersedes / replaces catalog reference: {part.supersededNumbers.join(', ')}</small> : null}
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

        <div className="pg-action-row">
          <button className="pg-primary" type="button" onClick={() => packetRef.current?.scrollIntoView({behavior: 'smooth'})}>
            Build repair packet <ChevronDown size={18} />
          </button>
          <button className="pg-secondary" type="button" onClick={resetRepair}><RotateCcw size={16} /> Reset demo</button>
        </div>
      </section>

      <section className="pg-camera-section">
        <div className="pg-section-heading compact">
          <div>
            <span className="pg-eyebrow">CAMERA INPUT — LOCAL V0 SHELL</span>
            <h2>Unknown part? Narrow first, recognize second.</h2>
            <p>The future recognizer will compare a photo only against parts valid for this vehicle and assembly. The current build intentionally performs no recognition and uploads nothing.</p>
          </div>
        </div>
        <div className="pg-camera-card">
          <label className="pg-upload">
            <Camera size={26} />
            <strong>{photoName || 'Take or choose a part photo'}</strong>
            <span>Browser-local preview only. No server upload, no API cost and no model call.</span>
            <input type="file" accept="image/*" capture="environment" onChange={(event) => onPhoto(event.target.files?.[0])} />
          </label>
          {photoUrl ? <img src={photoUrl} alt="Local part preview" className="pg-photo-preview" /> : (
            <div className="pg-camera-rules">
              <strong>Planned recognition evidence</strong>
              <span>3 angles</span><span>mounting holes / ports</span><span>OCR on visible markings</span><span>reference scale when possible</span><span>candidate set constrained by vehicle + assembly</span>
            </div>
          )}
        </div>
      </section>

      <div ref={packetRef} />
      <section className="pg-packet">
        <div className="pg-section-heading">
          <div>
            <span className="pg-eyebrow">REPAIR PACKET</span>
            <h2>{needed.length} items marked “Need”</h2>
            <p>{unresolved.length} unresolved · {inspect.length} to inspect before ordering</p>
          </div>
          <div className="pg-packet-status"><PackageCheck size={22} /> graph valid: {graphErrors.length === 0 ? 'yes' : 'no'}</div>
        </div>

        <div className="pg-summary-grid">
          <article><strong>{needed.length}</strong><span>add to package</span></article>
          <article><strong>{inspect.length}</strong><span>inspect first</span></article>
          <article><strong>{unresolved.length}</strong><span>not decided</span></article>
          <article><strong>{demoRelations.length}</strong><span>typed relationships</span></article>
        </div>

        <div className="pg-two-col">
          <div className="pg-panel">
            <div className="pg-panel-title"><ShoppingCart size={19} /><div><strong>Parts + five-source finder</strong><span>Main radiator has five researched product paths. Other verified parts fall back to exact-OEM-number searches until provider APIs/adapters exist.</span></div></div>
            {needed.map(({part}) => (
              <div className="pg-shopping-part" key={part.id}>
                <div className="pg-shopping-heading">
                  <div><strong>{part.name}</strong><span>Qty {part.quantity}</span></div>
                  <span className={`pg-source-status pg-source-status--${part.source.status}`}>{part.source.status}</span>
                </div>
                <div className="pg-oem-row"><span>OEM identity</span><strong>{part.oemNumber ?? 'LOCKED — authoritative source required'}</strong></div>
                <div className="pg-sellers">
                  {commerceSources.map((source) => {
                    const url = sellerUrl(part, source);
                    const direct = part.purchaseLinks?.some((link) => link.name === source.name);
                    return url ? (
                      <a key={source.id} href={url} target="_blank" rel="noreferrer" title={direct ? 'Researched product/catalog link' : `Exact OEM-number search for ${part.oemNumber}`}>
                        <ExternalLink size={14} />{source.name}<small>{direct ? 'direct' : 'OEM search'}</small>
                      </a>
                    ) : (
                      <button key={source.id} type="button" disabled title="OEM number not source-verified"><Search size={14} />{source.name}</button>
                    );
                  })}
                </div>
                <div className="pg-source-footer">
                  <small>{part.source.note}</small>
                  {part.source.url ? <a href={part.source.url} target="_blank" rel="noreferrer">Open source <ExternalLink size={12} /></a> : null}
                </div>
              </div>
            ))}
          </div>

          <div className="pg-panel">
            <div className="pg-panel-title"><Wrench size={19} /><div><strong>Repair intelligence</strong><span>Part identity can advance independently from safety-critical service specifications.</span></div></div>
            <div className="pg-spec-grid">
              <div><span>OEM part identity</span><strong>{verifiedParts} records catalog-backed</strong></div>
              <div><span>Supersessions</span><strong>Tracked when the catalog exposes them</strong></div>
              <div><span>Tools</span><strong>Pending service-source verification</strong></div>
              <div><span>Fastener torque</span><strong>Locked</strong></div>
              <div><span>Coolant type / quantity</span><strong>Locked</strong></div>
              <div><span>Drain / refill points</span><strong>Locked</strong></div>
              <div><span>Bleed procedure</span><strong>Locked</strong></div>
              <div><span>Pressure / flow notes</span><strong>Locked</strong></div>
              <div><span>Safety class</span><strong>Cooling + adjacent A/C / hybrid context</strong></div>
              <div><span>Runtime LLM tokens</span><strong>0</strong></div>
            </div>
            <div className="pg-safety-note"><XCircle size={18} /><span>PartGraph must be allowed to stop. No unverified torque, refrigerant, high-voltage or mechanical procedure is invented to make a page look complete.</span></div>
          </div>
        </div>
      </section>

      <section className="pg-source-ledger">
        <div className="pg-section-heading compact">
          <div>
            <span className="pg-eyebrow">SOURCE LEDGER</span>
            <h2>Every mechanical fact needs a trail.</h2>
            <p>This is the first primitive of the production data pipeline: source → structured claim → human/validator approval → versioned graph.</p>
          </div>
        </div>
        <div className="pg-ledger-grid">
          {sourceLedger.map((source) => (
            <a key={source.id} href={source.url} target="_blank" rel="noreferrer" className="pg-ledger-card">
              <ShieldCheck size={18} />
              <div><strong>{source.label}</strong><span>{source.scope}</span></div>
              <ExternalLink size={15} />
            </a>
          ))}
        </div>
      </section>

      <section className="pg-exploded">
        <div className="pg-section-heading compact">
          <div>
            <span className="pg-eyebrow">LOGICAL EXPLODED VIEW</span>
            <h2>One graph, multiple outputs.</h2>
            <p>The same typed relationships drive the checklist, shopping package and diagram. Geometry is deliberately schematic until licensed/verified CAD or dimensional data exists.</p>
          </div>
        </div>
        <Diagram states={states} />
      </section>

      <section className="pg-architecture">
        <div>
          <span className="pg-eyebrow">TOKEN / COMPUTE DESIGN</span>
          <h2>Runtime AI is off by default.</h2>
          <p>Mechanical truth is precomputed and cached. Seller search is exact-number retrieval. Vision will use local/constrained inference. LLMs belong in the internal source-ingestion pipeline only when deterministic extraction is ambiguous.</p>
        </div>
        <div className="pg-architecture-flow">
          <span>source ledger</span><b>→</b><span>verified JSON / DB graph</span><b>→</b><span>repair engine</span><b>→</b><span>browser workflow</span><b>→</b><span>seller adapters</span>
        </div>
      </section>

      <footer className="pg-footer">
        <strong>PartGraph Honda MVP</strong>
        <span>Static V0 · exact-vehicle catalog data where marked verified · no live OEM feed · no seller API · no AI inference · service specifications remain gated</span>
      </footer>
    </main>
  );
}
