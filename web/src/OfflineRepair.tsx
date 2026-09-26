import type { OfflineRepairPack } from './offline-repair'
import './offline-repair.css'

type OfflineSection = 'resume' | 'readiness' | 'guidance' | 'completion' | 'log'

function when(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function vehicleLabel(pack: OfflineRepairPack): string {
  const vehicle = pack.resume.vehicle
  const identity = vehicle.identity
  return vehicle.nickname || [identity.year, identity.make, identity.model, identity.trim].filter(Boolean).join(' ')
}

function ResumeSection({ pack }: { pack: OfflineRepairPack }) {
  const view = pack.resume.reorientation
  if (!view) return <p className="offline-repair-empty">No cached reorientation snapshot is available.</p>
  return (
    <>
      <div className="offline-repair-grid">
        <article><span>Last checkpoint</span><strong>{view.checkpoint.label}</strong><small>{when(view.checkpoint.created_at)}</small></article>
        <article><span>Next verified action</span><strong>{view.next_verified_action.label || 'Unavailable'}</strong><small>{view.next_verified_action.reason || view.next_verified_action.status}</small></article>
        <article><span>Readiness blockers</span><strong>{view.counts.verified_readiness_blockers}</strong><small>at last sync</small></article>
        <article><span>Repair sequence</span><strong>{pack.server_sequence}</strong><small>server-confirmed event</small></article>
      </div>
      <h3>Needs attention</h3>
      {view.attention.length === 0 ? <p className="offline-repair-empty">No cached attention items.</p> : (
        <div className="offline-repair-list">
          {view.attention.map((item) => (
            <article key={`${item.kind}-${item.id}`}>
              <div><strong>{item.label}</strong><span>{item.state}</span></div>
              {item.detail && <p>{item.detail}</p>}
            </article>
          ))}
        </div>
      )}
    </>
  )
}

function ReadinessSection({ pack }: { pack: OfflineRepairPack }) {
  const summary = pack.readiness.summary
  return (
    <>
      <div className="offline-repair-grid">
        <article><span>Ready</span><strong>{summary.ready}</strong><small>of {summary.total}</small></article>
        <article><span>Missing</span><strong>{summary.missing}</strong><small>last synced state</small></article>
        <article><span>Ordered</span><strong>{summary.ordered}</strong><small>last synced state</small></article>
        <article><span>Blocked</span><strong>{summary.blocked}</strong><small>required items</small></article>
      </div>
      <div className="offline-repair-list">
        {pack.readiness.requirements.map((item) => (
          <article key={item.requirement_definition_id}>
            <div><strong>{item.display_name}</strong><span>{item.readiness_state}</span></div>
            <p>{item.category} · source {item.readiness_source}{item.required_quantity !== null ? ` · need ${item.required_quantity}${item.unit ? ` ${item.unit}` : ''}` : ''}</p>
            {item.notes && <small>{item.notes}</small>}
          </article>
        ))}
      </div>
    </>
  )
}

function GuidanceSection({ pack }: { pack: OfflineRepairPack }) {
  const currentId = pack.guidance.current_action?.action_id
  return (
    <>
      <div className="offline-repair-grid">
        <article><span>Completed</span><strong>{pack.guidance.summary.completed}</strong><small>of {pack.guidance.summary.total}</small></article>
        <article><span>Pending</span><strong>{pack.guidance.summary.pending}</strong><small>cached plan</small></article>
        <article><span>Blocked</span><strong>{pack.guidance.summary.blocked}</strong><small>cached plan</small></article>
        <article><span>Plan status</span><strong>{pack.guidance.status.replaceAll('_', ' ')}</strong><small>read only</small></article>
      </div>
      <div className="offline-repair-actions">
        {pack.guidance.actions.map((action, index) => (
          <article key={action.action_id} className={action.action_id === currentId ? 'offline-repair-action offline-repair-action--current' : 'offline-repair-action'}>
            <header><span>{index + 1}</span><div><strong>{action.title}</strong><small>{action.progress_state}</small></div></header>
            <p>{action.instruction}</p>
            {action.warning_text && <p className="offline-repair-warning">{action.warning_text}</p>}
            {action.boundary_code && <p className="offline-repair-boundary">Unsupported boundary · {action.boundary_code}</p>}
            {action.inventory_blockers.length > 0 && <small>Inventory blockers: {action.inventory_blockers.map((item) => item.display_name).join(', ')}</small>}
          </article>
        ))}
      </div>
    </>
  )
}

function CompletionSection({ pack }: { pack: OfflineRepairPack }) {
  return (
    <div className="offline-repair-completion">
      <strong>{pack.guidance.procedure_complete ? 'Guided procedure was complete at last sync.' : 'Guided procedure was not complete at last sync.'}</strong>
      <p>PartGraph does not finalize repair completion while offline. Downstream requirements and server state must be rechecked after connectivity returns.</p>
    </div>
  )
}

function LogSection({ pack }: { pack: OfflineRepairPack }) {
  const activity = pack.resume.reorientation?.recent_activity ?? []
  return activity.length === 0 ? <p className="offline-repair-empty">No cached activity is available.</p> : (
    <div className="offline-repair-list">
      {activity.map((item) => <article key={item.sequence}><div><strong>{item.label}</strong><span>#{item.sequence}</span></div><small>{when(item.created_at)}</small></article>)}
      <p className="offline-repair-note">Only the cached recent activity is shown offline. The full event history remains server-authoritative.</p>
    </div>
  )
}

export function OfflineRepairWorkspace({ pack, section }: { pack: OfflineRepairPack; section: OfflineSection }) {
  const sectionTitle = section === 'resume' ? 'Repair overview' : section === 'log' ? 'Repair log' : section[0].toUpperCase() + section.slice(1)
  return (
    <main className="repair-workspace offline-repair-workspace">
      <header className="offline-repair-header">
        <div><p>OFFLINE PACK · READ ONLY</p><h1>{sectionTitle}</h1><strong>{pack.resume.session.title}</strong><span>{vehicleLabel(pack)}</span></div>
        <div className="offline-repair-meta"><span>Last sync {when(pack.generated_at)}</span><span>Definition v{pack.repair_definition_version}</span><span>{pack.pack_version}</span></div>
      </header>
      {section === 'resume' && <ResumeSection pack={pack} />}
      {section === 'readiness' && <ReadinessSection pack={pack} />}
      {section === 'guidance' && <GuidanceSection pack={pack} />}
      {section === 'completion' && <CompletionSection pack={pack} />}
      {section === 'log' && <LogSection pack={pack} />}
    </main>
  )
}
