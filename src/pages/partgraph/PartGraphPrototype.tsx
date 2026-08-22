import {useMemo, useRef, useState} from 'react';
import {
  Camera,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  Database,
  ExternalLink,
  Gauge,
  PackageCheck,
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
  type PartNode,
  type PartState,
} from '../../data/partGraphDemo';
import {buildRepairLines, completenessScore, questionForPart, validateGraph} from '../../lib/repairEngine';

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

function statusClass(state: PartState) {
  return `pg-state pg-state--${state}`;
}

function sellerUrl(part: PartNode, sourceId: string) {
  if (!part.oemNumber) return null;
  const q = encodeURIComponent(part.oemNumber);
  if (sourceId === 'ebay') return `https://www.ebay.com/sch/i.html?_nkw=${q}`;
  if (sourceId === 'honda') return `https://www.google.com/search?q=${encodeURIComponent(`site:dreamshop.honda.com ${part.oemNumber}`)}`;
  return `https://www.google.com/search?q=${encodeURIComponent(`${part.oemNumber} ${part.name}`)}`;
}

function Diagram({states}: {states: Record<string, PartState>}) {
  const byId = useMemo(() => new Map(demoParts.map((part) => [part.id, part])), []);
  return (
    <div className="pg-diagram-wrap" aria-label="Logical exploded assembly diagram">
      <svg viewBox="0 0 820 540" className="pg-diagram" role="img">
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
          return <line key={`${relation.from}-${relation.to}-${index}`} x1={x1} y1={y1} x2={x2} y2={y2} className="pg-edge" markerEnd="url(#arrow)" />;
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
        Logical relationship diagram only. It does not claim millimeter-accurate Honda geometry.
      </div>
    </div>
  );
}

export function PartGraphPrototype() {
  const [states, setStates] = useState<Record<string, PartState>>(initialPartStates);
  const [photoName, setPhotoName] = useState<string>('');
  const [photoUrl, setPhotoUrl] = useState<string>('');
  const packetRef = useRef<HTMLDivElement>(null);

  const lines = useMemo(() => buildRepairLines(demoParts, states), [states]);
  const score = useMemo(() => completenessScore(lines), [lines]);
  const graphErrors = useMemo(() => validateGraph(demoParts, demoRelations), []);
  const needed = lines.filter((line) => line.state === 'need');
  const unresolved = lines.filter((line) => line.state === 'not-sure');
  const inspect = lines.filter((line) => line.state === 'inspect');

  const changeState = (id: string, state: PartState) => {
    setStates((current) => ({...current, [id]: state}));
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
            <span>Honda-only engineering prototype</span>
          </div>
        </div>
        <div className="pg-header-badges">
          <span><Database size={15} /> deterministic graph</span>
          <span><Gauge size={15} /> 0 runtime LLM calls</span>
        </div>
      </header>

      <section className="pg-hero">
        <div className="pg-kicker">COMPLETE THE REPAIR, NOT JUST THE CART</div>
        <h1>Reconstruct the whole assembly before you order.</h1>
        <p>
          This first code slice turns one Honda radiator-area repair into a deterministic workflow: vehicle → block → sub-block → target part → connected-part checklist → repair packet.
        </p>
        <div className="pg-truth-banner">
          <ShieldCheck size={21} />
          <div><strong>Prototype truth boundary</strong><span>OEM numbers, torque values and fluid quantities stay locked until a source ledger verifies them. The UI is allowed to say “unknown.”</span></div>
        </div>
      </section>

      <section className="pg-workflow" aria-label="Repair selection workflow">
        <div className="pg-step pg-step--done"><span>1</span><div><small>Vehicle</small><strong>{demoVehicle.year} {demoVehicle.make} {demoVehicle.model}</strong><em>{demoVehicle.trim} {demoVehicle.body} · {demoVehicle.engine} · {demoVehicle.market}</em></div></div>
        <div className="pg-step pg-step--done"><span>2</span><div><small>Block</small><strong>Cooling</strong><em>Engine cooling system</em></div></div>
        <div className="pg-step pg-step--done"><span>3</span><div><small>Sub-block</small><strong>Front cooling module</strong><em>Radiator / fan / condenser area</em></div></div>
        <div className="pg-step pg-step--active"><span>4</span><div><small>Target part</small><strong>Radiator</strong><em>Selected repair anchor</em></div></div>
      </section>

      <section className="pg-check-section">
        <div className="pg-section-heading">
          <div>
            <span className="pg-eyebrow">ASSEMBLY CHECK</span>
            <h2>Tell us what survived.</h2>
            <p>The graph creates the questions. No language model is needed.</p>
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
                  <div className={statusClass(state)}><Icon size={16} /> {stateLabels[state]}</div>
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

        <button className="pg-primary" type="button" onClick={() => packetRef.current?.scrollIntoView({behavior: 'smooth'})}>
          Build repair packet <ChevronDown size={18} />
        </button>
      </section>

      <section className="pg-camera-section">
        <div className="pg-section-heading compact">
          <div>
            <span className="pg-eyebrow">CAMERA INPUT — PHASE 3 SHELL</span>
            <h2>Unknown part? Narrow first, recognize second.</h2>
            <p>The production recognizer will compare a photo only against parts valid for this vehicle and assembly.</p>
          </div>
        </div>
        <div className="pg-camera-card">
          <label className="pg-upload">
            <Camera size={26} />
            <strong>{photoName || 'Take or choose a part photo'}</strong>
            <span>Local preview only in this prototype. No upload or model call occurs.</span>
            <input type="file" accept="image/*" capture="environment" onChange={(event) => onPhoto(event.target.files?.[0])} />
          </label>
          {photoUrl ? <img src={photoUrl} alt="Local part preview" className="pg-photo-preview" /> : (
            <div className="pg-camera-rules">
              <strong>Planned evidence</strong>
              <span>3 angles</span><span>mounting holes / ports</span><span>OCR on visible markings</span><span>reference scale when possible</span>
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
            <div className="pg-panel-title"><ShoppingCart size={19} /><div><strong>Parts + five-source finder</strong><span>Search unlocks only when OEM identity is verified.</span></div></div>
            {needed.map(({part}) => (
              <div className="pg-shopping-part" key={part.id}>
                <div className="pg-shopping-heading">
                  <div><strong>{part.name}</strong><span>Qty {part.quantity}</span></div>
                  <span className={`pg-source-status pg-source-status--${part.source.status}`}>{part.source.status}</span>
                </div>
                <div className="pg-oem-row"><span>OEM identity</span><strong>{part.oemNumber ?? 'LOCKED — source verification required'}</strong></div>
                <div className="pg-sellers">
                  {commerceSources.map((source) => {
                    const url = sellerUrl(part, source.id);
                    return url ? (
                      <a key={source.id} href={url} target="_blank" rel="noreferrer"><ExternalLink size={14} />{source.name}</a>
                    ) : (
                      <button key={source.id} type="button" disabled title="OEM number not verified"><Search size={14} />{source.name}</button>
                    );
                  })}
                </div>
                <small className="pg-source-note">{part.source.note}</small>
              </div>
            ))}
          </div>

          <div className="pg-panel">
            <div className="pg-panel-title"><Wrench size={19} /><div><strong>Repair intelligence</strong><span>Engineering fields exist before values are allowed in.</span></div></div>
            <div className="pg-spec-grid">
              <div><span>Tools</span><strong>Pending source verification</strong></div>
              <div><span>Fastener sizes</span><strong>Pending source verification</strong></div>
              <div><span>Torque</span><strong>Pending source verification</strong></div>
              <div><span>Coolant type / quantity</span><strong>Pending source verification</strong></div>
              <div><span>Drain / refill points</span><strong>Pending source verification</strong></div>
              <div><span>Bleed procedure</span><strong>Pending source verification</strong></div>
              <div><span>Pressure / flow notes</span><strong>Pending source verification</strong></div>
              <div><span>Safety class</span><strong>Cooling + adjacent A/C / hybrid context</strong></div>
            </div>
            <div className="pg-safety-note"><XCircle size={18} /><span>The prototype intentionally refuses to invent torque, refrigerant, high-voltage or mechanical specifications.</span></div>
          </div>
        </div>
      </section>

      <section className="pg-exploded">
        <div className="pg-section-heading compact">
          <div>
            <span className="pg-eyebrow">LOGICAL EXPLODED VIEW</span>
            <h2>One graph, multiple outputs.</h2>
            <p>The same typed relationships drive the checklist, shopping package and diagram.</p>
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
          <span>verified JSON / DB graph</span><b>→</b><span>repair engine</span><b>→</b><span>browser workflow</span><b>→</b><span>seller adapters</span>
        </div>
      </section>

      <footer className="pg-footer">
        <strong>PartGraph engineering prototype</strong>
        <span>Static demo · no live OEM feed · no live seller API · no AI inference · no repair specification claims</span>
      </footer>
    </main>
  );
}
