import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiRequest, formatApiFailure } from './api'
import { repairMutationHeaders } from './repair-client'
import './repair-workspaces.css'

type SessionStatus = 'active' | 'paused' | 'archived'
type LeaseStatus = 'available' | 'owned' | 'held_by_other'
type RepairSession = {
  id: string
  user_vehicle_id: string
  title: string
  status: SessionStatus
  current_sequence: number
  updated_at: string
}
type ResumeSnapshot = {
  session: RepairSession
  vehicle: {
    id: string
    nickname: string | null
    identity: { year: number; make: string; model: string; trim: string | null }
  }
  lease: { status: LeaseStatus; can_edit: boolean; expires_at: string | null }
  reorientation: null | {
    checkpoint: { sequence: number; event_type: string; label: string; created_at: string }
    attention: Array<{ kind: string; id: string; label: string; state: string; severity: string; detail: string | null }>
    storage_groups: Array<{ storage_location_id: string; label: string; item_count: number }>
    recent_observations: Array<{ id: string; category: string; text: string; created_at: string }>
    recent_evidence: Array<{ id: string; purpose: string; content_url: string; created_at: string }>
    recent_activity: Array<{ sequence: number; event_type: string; label: string; created_at: string }>
    counts: {
      fasteners_total: number
      hardware_not_installed: number
      hardware_stored: number
      hardware_loose: number
      inventory_total: number
      procurement_blockers: number
      observations_total: number
      photos_total: number
    }
    next_verified_action: { status: 'available' | 'unavailable'; label: string | null; reason: string | null }
  }
}

function vehicleLabel(snapshot: ResumeSnapshot) {
  const identity = snapshot.vehicle.identity
  return snapshot.vehicle.nickname || [identity.year, identity.make, identity.model, identity.trim].filter(Boolean).join(' ')
}

export function ResumeRepairWorkspace({
  onStartRepair,
  onOpenGarage,
  onOpenGuidance,
  onOpenLog,
}: {
  onStartRepair: () => void
  onOpenGarage: () => void
  onOpenGuidance: () => void
  onOpenLog: () => void
}) {
  const [sessions, setSessions] = useState<RepairSession[]>([])
  const [selectedId, setSelectedId] = useState(() => window.sessionStorage.getItem('partgraph:active-repair-session') || '')
  const [snapshot, setSnapshot] = useState<ResumeSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSessions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const rows = await apiRequest<RepairSession[]>('/api/v1/repair-sessions', undefined, { retryIdempotent: true })
      setSessions(rows)
      setSelectedId((current) => {
        if (current && rows.some((row) => row.id === current)) return current
        return rows[0]?.id || ''
      })
    } catch (failure) {
      setSessions([])
      setError(formatApiFailure(failure, 'Could not load repair sessions.'))
    } finally {
      setLoading(false)
    }
  }, [])

  const loadSnapshot = useCallback(async (sessionId: string) => {
    if (!sessionId) {
      setSnapshot(null)
      return
    }
    setError(null)
    try {
      const value = await apiRequest<ResumeSnapshot>(`/api/v1/repair-sessions/${sessionId}/resume`, undefined, { retryIdempotent: true })
      setSnapshot(value)
      window.sessionStorage.setItem('partgraph:active-repair-session', sessionId)
    } catch (failure) {
      setSnapshot(null)
      setError(formatApiFailure(failure, 'Could not build the repair resume view.'))
    }
  }, [])

  useEffect(() => { void loadSessions() }, [loadSessions])
  useEffect(() => { void loadSnapshot(selectedId) }, [selectedId, loadSnapshot])

  useEffect(() => {
    const refresh = () => void loadSessions()
    window.addEventListener('partgraph:repair-sessions-changed', refresh)
    return () => window.removeEventListener('partgraph:repair-sessions-changed', refresh)
  }, [loadSessions])

  const selectedSession = useMemo(() => sessions.find((session) => session.id === selectedId) || null, [sessions, selectedId])

  async function leaseAction(action: 'acquire' | 'takeover') {
    if (!selectedId) return
    setBusy(true)
    setError(null)
    try {
      await apiRequest(`/api/v1/repair-sessions/${selectedId}/lease/${action}`, { method: 'POST', headers: repairMutationHeaders() })
      await loadSnapshot(selectedId)
    } catch (failure) {
      setError(formatApiFailure(failure, `Could not ${action === 'acquire' ? 'acquire' : 'take over'} the edit lease.`))
    } finally {
      setBusy(false)
    }
  }

  async function mutateSession(action: 'pause' | 'resume' | 'archive') {
    if (!selectedId) return
    setBusy(true)
    setError(null)
    try {
      await apiRequest(`/api/v1/repair-sessions/${selectedId}/${action}`, {
        method: action === 'archive' ? 'PATCH' : 'POST',
        headers: repairMutationHeaders(),
      })
      window.dispatchEvent(new CustomEvent('partgraph:repair-sessions-changed'))
      await loadSessions()
      if (action !== 'archive') await loadSnapshot(selectedId)
    } catch (failure) {
      setError(formatApiFailure(failure, `Could not ${action} this repair.`))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="repair-workspace-shell">
      <header className="workspace-hero repair-hero-row">
        <div><p className="eyebrow">PARTGRAPH · RESUME</p><h1>Return to the repair exactly where work stopped.</h1><p>Resume prioritizes current state, loose hardware, blockers, recent evidence, and the next verified action instead of making you reconstruct the job from memory.</p></div>
        <button type="button" onClick={onStartRepair}>Start a new repair</button>
      </header>

      <section className="repair-panel panel">
        <div className="section-heading-row">
          <div><p className="eyebrow">REPAIR SESSIONS</p><h2>Choose a repair</h2></div>
          {sessions.length > 0 && <select aria-label="Repair session" value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>{sessions.map((session) => <option key={session.id} value={session.id}>{session.title} · {session.status}</option>)}</select>}
        </div>
        {loading && <p className="muted">Loading repairs…</p>}
        {!loading && sessions.length === 0 && <div className="repair-empty"><h2>No repair sessions yet</h2><p>Start from a saved garage vehicle. The new session will then appear here for continuity.</p><div className="repair-button-row"><button type="button" onClick={onStartRepair}>Start repair</button><button type="button" className="secondary" onClick={onOpenGarage}>Open Garage</button></div></div>}
        {error && <div className="workspace-alert workspace-alert--error">{error}</div>}
      </section>

      {snapshot && selectedSession && (
        <>
          <section className="repair-panel panel">
            <div className="section-heading-row"><div><p className="eyebrow">{snapshot.session.status.toUpperCase()} · SEQUENCE {snapshot.session.current_sequence}</p><h2>{snapshot.session.title}</h2><p>{vehicleLabel(snapshot)}</p></div><span className={`status-pill status-pill--${snapshot.lease.can_edit ? 'ok' : 'warn'}`}>{snapshot.lease.can_edit ? 'Editable on this device' : snapshot.lease.status.replaceAll('_', ' ')}</span></div>
            <div className="repair-button-row">
              {!snapshot.lease.can_edit && snapshot.lease.status !== 'held_by_other' && <button type="button" disabled={busy} onClick={() => void leaseAction('acquire')}>Acquire edit lease</button>}
              {!snapshot.lease.can_edit && snapshot.lease.status === 'held_by_other' && <button type="button" disabled={busy} onClick={() => void leaseAction('takeover')}>Take over edit lease</button>}
              {snapshot.session.status === 'active' && <button type="button" className="secondary" disabled={busy || !snapshot.lease.can_edit} onClick={() => void mutateSession('pause')}>Pause repair</button>}
              {snapshot.session.status === 'paused' && <button type="button" disabled={busy || !snapshot.lease.can_edit} onClick={() => void mutateSession('resume')}>Resume repair</button>}
              {snapshot.session.status !== 'archived' && <button type="button" className="secondary" disabled={busy || !snapshot.lease.can_edit} onClick={() => void mutateSession('archive')}>Archive repair</button>}
              <button type="button" onClick={onOpenGuidance}>Open guided repair</button>
              <button type="button" className="secondary" onClick={onOpenLog}>Open repair log</button>
            </div>
          </section>

          {snapshot.reorientation && (
            <section className="repair-dashboard-grid">
              <article className="repair-panel panel repair-span-2">
                <p className="eyebrow">CHECKPOINT</p><h2>{snapshot.reorientation.checkpoint.label}</h2><p>Last durable event: {snapshot.reorientation.checkpoint.event_type.replaceAll('_', ' ')} · sequence {snapshot.reorientation.checkpoint.sequence}</p>
                <div className="next-action-card"><strong>Next verified action</strong>{snapshot.reorientation.next_verified_action.status === 'available' ? <span>{snapshot.reorientation.next_verified_action.label}</span> : <span>{snapshot.reorientation.next_verified_action.reason || 'No verified next action is available.'}</span>}</div>
              </article>
              <article className="repair-panel panel"><p className="eyebrow">REPAIR MEMORY</p><h3>Tracked state</h3><dl className="count-grid"><div><dt>Fasteners</dt><dd>{snapshot.reorientation.counts.fasteners_total}</dd></div><div><dt>Not installed</dt><dd>{snapshot.reorientation.counts.hardware_not_installed}</dd></div><div><dt>Inventory</dt><dd>{snapshot.reorientation.counts.inventory_total}</dd></div><div><dt>Blockers</dt><dd>{snapshot.reorientation.counts.procurement_blockers}</dd></div><div><dt>Observations</dt><dd>{snapshot.reorientation.counts.observations_total}</dd></div><div><dt>Photos</dt><dd>{snapshot.reorientation.counts.photos_total}</dd></div></dl></article>
              <article className="repair-panel panel"><p className="eyebrow">ATTENTION</p><h3>What still needs attention</h3>{snapshot.reorientation.attention.length === 0 ? <p className="muted">Nothing flagged.</p> : <ul className="repair-list">{snapshot.reorientation.attention.map((item) => <li key={`${item.kind}-${item.id}`}><strong>{item.label}</strong><span>{item.state} · {item.severity}</span>{item.detail && <small>{item.detail}</small>}</li>)}</ul>}</article>
              <article className="repair-panel panel"><p className="eyebrow">STORAGE</p><h3>Where hardware is stored</h3>{snapshot.reorientation.storage_groups.length === 0 ? <p className="muted">No stored groups.</p> : <ul className="repair-list">{snapshot.reorientation.storage_groups.map((group) => <li key={group.storage_location_id}><strong>{group.label}</strong><span>{group.item_count} item{group.item_count === 1 ? '' : 's'}</span></li>)}</ul>}</article>
              <article className="repair-panel panel"><p className="eyebrow">RECENT OBSERVATIONS</p><h3>Latest notes</h3>{snapshot.reorientation.recent_observations.length === 0 ? <p className="muted">No observations yet.</p> : <ul className="repair-list">{snapshot.reorientation.recent_observations.map((observation) => <li key={observation.id}><strong>{observation.category.replaceAll('_', ' ')}</strong><span>{observation.text}</span></li>)}</ul>}</article>
            </section>
          )}
        </>
      )}
    </main>
  )
}
