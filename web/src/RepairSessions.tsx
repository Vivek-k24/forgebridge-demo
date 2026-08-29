import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { apiRequest, CSRF_HEADERS, formatApiFailure } from './api'
import { newIdempotencyKey, partGraphDeviceId } from './device'
import './repair-sessions.css'

type SessionStatus = 'active' | 'paused' | 'archived'
type LeaseStatus = 'available' | 'owned' | 'held_by_other'
type RepairEventType =
  | 'session_started'
  | 'session_paused'
  | 'session_resumed'
  | 'session_archived'
  | 'storage_location_created'
  | 'fastener_recorded'
  | 'fastener_state_changed'
  | 'inventory_item_recorded'
  | 'inventory_state_changed'
  | 'observation_recorded'
  | 'photo_evidence_added'
  | 'photo_evidence_deleted'

type VehicleIdentity = {
  year: number
  market: string
  make: string
  model: string
  generation: string | null
  trim: string | null
  body_style: string | null
  engine: string | null
  transmission: string | null
  drivetrain: string | null
}

type UserVehicle = {
  id: string
  nickname: string | null
  identity: VehicleIdentity
  masked_vin: string | null
  archived_at: string | null
}

type RepairSession = {
  id: string
  user_vehicle_id: string
  title: string
  status: SessionStatus
  current_sequence: number
  archived_at: string | null
  created_at: string
  updated_at: string
}

type RepairEvent = {
  id: string
  session_id: string
  sequence: number
  event_type: RepairEventType
  actor_device_id: string
  payload: Record<string, unknown>
  created_at: string
}

type Lease = {
  status: LeaseStatus
  can_edit: boolean
  expires_at: string | null
}

type ResumeActivity = {
  sequence: number
  event_type: RepairEventType
  label: string
  created_at: string
}

type ResumeAttention = {
  kind: 'fastener' | 'inventory' | 'observation'
  id: string
  label: string
  state: string
  severity: 'attention' | 'waiting' | 'blocking'
  detail: string | null
}

type ResumeStorageGroup = {
  storage_location_id: string
  label: string
  item_count: number
}

type ResumeObservation = {
  id: string
  category: string
  text: string
  fastener_id: string | null
  created_at: string
}

type ResumeEvidence = {
  id: string
  purpose: string
  content_url: string
  created_at: string
}

type ResumeCounts = {
  fasteners_total: number
  hardware_not_installed: number
  hardware_stored: number
  hardware_loose: number
  inventory_total: number
  procurement_blockers: number
  observations_total: number
  photos_total: number
}

type Reorientation = {
  checkpoint: ResumeActivity
  attention: ResumeAttention[]
  storage_groups: ResumeStorageGroup[]
  recent_observations: ResumeObservation[]
  recent_evidence: ResumeEvidence[]
  recent_activity: ResumeActivity[]
  counts: ResumeCounts
  next_verified_action: {
    status: 'available' | 'unavailable'
    label: string | null
    reason: string | null
  }
}

type ResumeSnapshot = {
  session: RepairSession
  vehicle: UserVehicle
  last_event: RepairEvent
  lease: Lease
  reorientation: Reorientation
}

type MutationResult = {
  session: RepairSession
  event: RepairEvent
  lease: Lease
}

function vehicleName(vehicle: UserVehicle): string {
  const identity = vehicle.identity
  const detail = [identity.year, identity.make, identity.model, identity.trim].filter(Boolean).join(' ')
  return vehicle.nickname ? `${vehicle.nickname} · ${detail}` : detail
}

function requestHeaders(deviceId: string, idempotencyKey?: string): Record<string, string> {
  return {
    ...CSRF_HEADERS,
    'X-PartGraph-Device-ID': deviceId,
    ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}),
  }
}

function stateLabel(value: string): string {
  return value.replaceAll('_', ' ')
}

function plural(value: number, singular: string, pluralValue = `${singular}s`): string {
  return `${value} ${value === 1 ? singular : pluralValue}`
}

export function RepairSessionWorkspace({ onOpenGarage }: { onOpenGarage: () => void }) {
  const deviceId = useMemo(() => partGraphDeviceId(), [])
  const [vehicles, setVehicles] = useState<UserVehicle[]>([])
  const [sessions, setSessions] = useState<RepairSession[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [snapshot, setSnapshot] = useState<ResumeSnapshot | null>(null)
  const [vehicleId, setVehicleId] = useState('')
  const [title, setTitle] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refreshLists = useCallback(async () => {
    const [vehicleRows, sessionRows] = await Promise.all([
      apiRequest<UserVehicle[]>('/api/v1/user-vehicles', {}, { retryIdempotent: true }),
      apiRequest<RepairSession[]>('/api/v1/repair-sessions', {}, { retryIdempotent: true }),
    ])
    setVehicles(vehicleRows)
    setSessions(sessionRows)
    setVehicleId((current) => current || vehicleRows[0]?.id || '')
    return sessionRows
  }, [])

  const loadSession = useCallback(
    async (sessionId: string) => {
      const resume = await apiRequest<ResumeSnapshot>(
        `/api/v1/repair-sessions/${sessionId}/resume`,
        { headers: { 'X-PartGraph-Device-ID': deviceId } },
        { retryIdempotent: true },
      )
      setSelectedId(sessionId)
      setSnapshot(resume)
    },
    [deviceId],
  )

  useEffect(() => {
    let active = true
    async function initialize() {
      try {
        setLoading(true)
        const rows = await refreshLists()
        if (!active) return
        if (rows[0]) await loadSession(rows[0].id)
      } catch (failure) {
        if (active) setError(formatApiFailure(failure, 'Could not load repair sessions.'))
      } finally {
        if (active) setLoading(false)
      }
    }
    void initialize()
    return () => {
      active = false
    }
  }, [loadSession, refreshLists])

  async function createSession(event: FormEvent) {
    event.preventDefault()
    if (!vehicleId || !title.trim()) return
    try {
      setBusy(true)
      setError(null)
      setMessage(null)
      const created = await apiRequest<ResumeSnapshot>('/api/v1/repair-sessions', {
        method: 'POST',
        headers: {
          ...requestHeaders(deviceId, newIdempotencyKey('repair_create')),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_vehicle_id: vehicleId, title: title.trim() }),
      })
      setTitle('')
      setSnapshot(created)
      setSelectedId(created.session.id)
      setMessage('Repair session started and saved to PartGraph.')
      await refreshLists()
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not start the repair session.'))
    } finally {
      setBusy(false)
    }
  }

  async function leaseAction(takeover: boolean) {
    if (!selectedId) return
    try {
      setBusy(true)
      setError(null)
      await apiRequest(`/api/v1/repair-sessions/${selectedId}/lease/${takeover ? 'takeover' : 'acquire'}`, {
        method: 'POST',
        headers: requestHeaders(deviceId),
      })
      setMessage(takeover ? 'Editing control moved to this device.' : 'Editing control acquired.')
      await loadSession(selectedId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not acquire editing control.'))
    } finally {
      setBusy(false)
    }
  }

  async function stateAction(action: 'pause' | 'resume' | 'archive') {
    if (!selectedId) return
    try {
      setBusy(true)
      setError(null)
      setMessage(null)
      const method = action === 'archive' ? 'PATCH' : 'POST'
      await apiRequest<MutationResult>(
        `/api/v1/repair-sessions/${selectedId}/${action}`,
        {
          method,
          headers: requestHeaders(deviceId, newIdempotencyKey(`repair_${action}`)),
        },
      )
      setMessage(
        action === 'pause'
          ? 'Repair paused. The resume point is saved.'
          : action === 'resume'
            ? 'Repair resumed on this device.'
            : 'Repair archived. Its event history is preserved.',
      )
      if (action === 'archive') {
        setSnapshot(null)
        setSelectedId(null)
        const rows = await refreshLists()
        if (rows[0]) await loadSession(rows[0].id)
      } else {
        await loadSession(selectedId)
        await refreshLists()
      }
    } catch (failure) {
      setError(formatApiFailure(failure, `Could not ${action} this repair session.`))
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return <p className="repair-loading">Reconstructing your repair state…</p>
  }

  return (
    <div className="repair-workspace">
      <header className="repair-heading">
        <div>
          <p className="eyebrow">PARTGRAPH · RESUME</p>
          <h1>See where the repair actually stopped.</h1>
          <p className="lede">
            PartGraph reconstructs what was recorded so you can look at the car and continue without
            maintaining a separate repair log.
          </p>
        </div>
        <span className="repair-device">device {deviceId.slice(0, 8)}</span>
      </header>

      {error && <div className="repair-alert repair-alert--error">{error}</div>}
      {message && <div className="repair-alert repair-alert--success">{message}</div>}

      <div className="repair-grid">
        <aside className="repair-sidebar panel">
          <div className="repair-section-title">
            <div>
              <p className="eyebrow">ACTIVE REPAIRS</p>
              <h2>Resume</h2>
            </div>
            <span>{sessions.length}</span>
          </div>

          {sessions.length === 0 ? (
            <div className="repair-empty">
              <strong>No active repair sessions.</strong>
              <p>Start one from a saved vehicle. Nothing is pre-filled or invented.</p>
            </div>
          ) : (
            <div className="repair-session-list">
              {sessions.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={item.id === selectedId ? 'repair-session-card repair-session-card--active' : 'repair-session-card'}
                  onClick={() => void loadSession(item.id)}
                >
                  <strong>{item.title}</strong>
                  <span>{item.status} · event {item.current_sequence}</span>
                </button>
              ))}
            </div>
          )}

          <form className="repair-create" onSubmit={createSession}>
            <p className="eyebrow">START REPAIR</p>
            {vehicles.length === 0 ? (
              <div className="repair-empty">
                <p>You need a saved vehicle before starting a repair session.</p>
                <button type="button" className="secondary" onClick={onOpenGarage}>Open garage</button>
              </div>
            ) : (
              <>
                <label>
                  <span>Vehicle</span>
                  <select value={vehicleId} onChange={(event) => setVehicleId(event.target.value)}>
                    {vehicles.map((vehicle) => (
                      <option key={vehicle.id} value={vehicle.id}>{vehicleName(vehicle)}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>What are you working on?</span>
                  <input
                    value={title}
                    maxLength={160}
                    placeholder="e.g. Replace front radiator"
                    onChange={(event) => setTitle(event.target.value)}
                  />
                </label>
                <button type="submit" disabled={busy || !vehicleId || !title.trim()}>Start repair</button>
              </>
            )}
          </form>
        </aside>

        <section className="repair-main panel">
          {!snapshot ? (
            <div className="repair-empty repair-empty--large">
              <p className="eyebrow">CURRENT STATE</p>
              <h2>No repair selected.</h2>
              <p>Select an active repair or start one. PartGraph will not fabricate a resume point.</p>
            </div>
          ) : (
            <ResumeState
              snapshot={snapshot}
              busy={busy}
              onLease={leaseAction}
              onState={stateAction}
            />
          )}
        </section>
      </div>
    </div>
  )
}

function ResumeState({
  snapshot,
  busy,
  onLease,
  onState,
}: {
  snapshot: ResumeSnapshot
  busy: boolean
  onLease: (takeover: boolean) => Promise<void>
  onState: (action: 'pause' | 'resume' | 'archive') => Promise<void>
}) {
  const resume = snapshot.reorientation
  const counts = resume.counts

  return (
    <>
      <div className="repair-current-head">
        <div>
          <p className="eyebrow">CURRENT STATE · EVENT {snapshot.session.current_sequence}</p>
          <h2>{snapshot.session.title}</h2>
          <p>{vehicleName(snapshot.vehicle)}</p>
        </div>
        <span className={`repair-status repair-status--${snapshot.session.status}`}>{snapshot.session.status}</span>
      </div>

      <section className="resume-glance" aria-label="Repair reorientation">
        <article className="resume-checkpoint">
          <span>Where you left it</span>
          <strong>{resume.checkpoint.label}</strong>
          <small>{new Date(resume.checkpoint.created_at).toLocaleString()}</small>
        </article>
        <article>
          <span>Hardware apart</span>
          <strong>{plural(counts.hardware_not_installed, 'item')} not installed</strong>
          <small>
            {plural(counts.hardware_stored, 'item')} grouped · {plural(counts.hardware_loose, 'item')} loose
          </small>
        </article>
        <article>
          <span>Waiting on parts</span>
          <strong>{plural(counts.procurement_blockers, 'record')} blocking or waiting</strong>
          <small>{plural(counts.inventory_total, 'inventory record')} total</small>
        </article>
      </section>

      <section className="resume-attention">
        <div className="repair-section-title">
          <div>
            <p className="eyebrow">LOOK FIRST</p>
            <h3>Recorded exceptions</h3>
          </div>
          <span>{resume.attention.length}</span>
        </div>
        {resume.attention.length === 0 ? (
          <div className="resume-clear">
            <strong>No recorded blockers or damage.</strong>
            <span>PartGraph has no missing/damaged hardware or procurement blocker recorded.</span>
          </div>
        ) : (
          <div className="resume-attention-list">
            {resume.attention.map((item) => (
              <article key={`${item.kind}-${item.id}`} className={`resume-attention-item resume-attention-item--${item.severity}`}>
                <div>
                  <span>{item.kind}</span>
                  <strong>{item.label}</strong>
                  {item.detail && <small>{item.detail}</small>}
                </div>
                <b>{stateLabel(item.state)}</b>
              </article>
            ))}
          </div>
        )}
      </section>

      {(resume.storage_groups.length > 0 || counts.hardware_loose > 0) && (
        <section className="resume-hardware">
          <div className="repair-section-title">
            <div>
              <p className="eyebrow">HARDWARE AT A GLANCE</p>
              <h3>Where things were left</h3>
            </div>
            <span>{counts.fasteners_total}</span>
          </div>
          <div className="resume-storage-list">
            {resume.storage_groups.map((group) => (
              <article key={group.storage_location_id}>
                <strong>{group.label}</strong>
                <span>{plural(group.item_count, 'item')} grouped here</span>
              </article>
            ))}
            {counts.hardware_loose > 0 && (
              <article>
                <strong>Visible / not assigned to storage</strong>
                <span>{plural(counts.hardware_loose, 'removed item')} recorded loose</span>
              </article>
            )}
          </div>
        </section>
      )}

      {(resume.recent_observations.length > 0 || resume.recent_evidence.length > 0) && (
        <section className="resume-context-grid">
          <div className="resume-context-card">
            <div className="repair-section-title">
              <div>
                <p className="eyebrow">NOTES</p>
                <h3>Recent observations</h3>
              </div>
              <span>{counts.observations_total}</span>
            </div>
            {resume.recent_observations.length === 0 ? (
              <p className="resume-muted">No confirmed observations recorded.</p>
            ) : (
              <div className="resume-note-list">
                {resume.recent_observations.map((item) => (
                  <article key={item.id}>
                    <span>{stateLabel(item.category)}</span>
                    <p>{item.text}</p>
                  </article>
                ))}
              </div>
            )}
          </div>

          <div className="resume-context-card">
            <div className="repair-section-title">
              <div>
                <p className="eyebrow">VISUAL MEMORY</p>
                <h3>Recent evidence</h3>
              </div>
              <span>{counts.photos_total}</span>
            </div>
            {resume.recent_evidence.length === 0 ? (
              <p className="resume-muted">No photo evidence recorded.</p>
            ) : (
              <div className="resume-photo-strip">
                {resume.recent_evidence.map((item) => (
                  <figure key={item.id}>
                    <img src={item.content_url} alt={`${stateLabel(item.purpose)} repair evidence`} />
                    <figcaption>{stateLabel(item.purpose)}</figcaption>
                  </figure>
                ))}
              </div>
            )}
          </div>
        </section>
      )}

      <section className="resume-next-action">
        <div>
          <span>Next verified action</span>
          <strong>
            {resume.next_verified_action.status === 'available'
              ? resume.next_verified_action.label
              : 'Not available yet'}
          </strong>
        </div>
        {resume.next_verified_action.status === 'unavailable' && (
          <small>
            PartGraph will not guess the next mechanical step. Verified repair-plan guidance arrives in the guidance domain.
          </small>
        )}
      </section>

      <div className="repair-actions">
        {snapshot.lease.status === 'available' && snapshot.session.status !== 'archived' && (
          <button disabled={busy} onClick={() => void onLease(false)}>Take editing control</button>
        )}
        {snapshot.lease.status === 'held_by_other' && snapshot.session.status !== 'archived' && (
          <button disabled={busy} onClick={() => void onLease(true)}>Take over session</button>
        )}
        {snapshot.lease.can_edit && snapshot.session.status === 'active' && (
          <button disabled={busy} onClick={() => void onState('pause')}>Pause repair</button>
        )}
        {snapshot.lease.can_edit && snapshot.session.status === 'paused' && (
          <button disabled={busy} onClick={() => void onState('resume')}>Resume work</button>
        )}
        {snapshot.lease.can_edit && snapshot.session.status !== 'archived' && (
          <button className="secondary" disabled={busy} onClick={() => void onState('archive')}>Archive</button>
        )}
        <span className="resume-lease-note">
          {snapshot.lease.can_edit ? 'Editing on this device.' : `View only · ${stateLabel(snapshot.lease.status)}`}
        </span>
      </div>

      <section className="resume-activity">
        <div className="repair-section-title">
          <div>
            <p className="eyebrow">RECENT ACTIVITY</p>
            <h3>Last recorded changes</h3>
          </div>
          <span>{resume.recent_activity.length}</span>
        </div>
        <ol>
          {[...resume.recent_activity].reverse().map((item) => (
            <li key={`${item.sequence}-${item.event_type}`}>
              <span>{item.sequence}</span>
              <div>
                <strong>{item.label}</strong>
                <small>{new Date(item.created_at).toLocaleString()}</small>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </>
  )
}
