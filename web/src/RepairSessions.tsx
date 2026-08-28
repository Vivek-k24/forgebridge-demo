import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { apiRequest, CSRF_HEADERS, formatApiFailure } from './api'
import { newIdempotencyKey, partGraphDeviceId } from './device'
import './repair-sessions.css'

type SessionStatus = 'active' | 'paused' | 'archived'
type LeaseStatus = 'available' | 'owned' | 'held_by_other'

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
  event_type: 'session_started' | 'session_paused' | 'session_resumed' | 'session_archived'
  actor_device_id: string
  payload: Record<string, unknown>
  created_at: string
}

type Lease = {
  status: LeaseStatus
  can_edit: boolean
  expires_at: string | null
}

type ResumeSnapshot = {
  session: RepairSession
  vehicle: UserVehicle
  last_event: RepairEvent
  lease: Lease
}

type MutationResult = {
  session: RepairSession
  event: RepairEvent
  lease: Lease
}

type EventPage = {
  items: RepairEvent[]
  next_after_sequence: number | null
}

function vehicleName(vehicle: UserVehicle): string {
  const identity = vehicle.identity
  const detail = [identity.year, identity.make, identity.model, identity.trim].filter(Boolean).join(' ')
  return vehicle.nickname ? `${vehicle.nickname} · ${detail}` : detail
}

function eventLabel(event: RepairEvent): string {
  const labels: Record<RepairEvent['event_type'], string> = {
    session_started: 'Repair started',
    session_paused: 'Repair paused',
    session_resumed: 'Repair resumed',
    session_archived: 'Repair archived',
  }
  return labels[event.event_type]
}

function requestHeaders(deviceId: string, idempotencyKey?: string): Record<string, string> {
  return {
    ...CSRF_HEADERS,
    'X-PartGraph-Device-ID': deviceId,
    ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}),
  }
}

export function RepairSessionWorkspace({ onOpenGarage }: { onOpenGarage: () => void }) {
  const deviceId = useMemo(() => partGraphDeviceId(), [])
  const [vehicles, setVehicles] = useState<UserVehicle[]>([])
  const [sessions, setSessions] = useState<RepairSession[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [snapshot, setSnapshot] = useState<ResumeSnapshot | null>(null)
  const [history, setHistory] = useState<RepairEvent[]>([])
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
      const [resume, events] = await Promise.all([
        apiRequest<ResumeSnapshot>(
          `/api/v1/repair-sessions/${sessionId}/resume`,
          { headers: { 'X-PartGraph-Device-ID': deviceId } },
          { retryIdempotent: true },
        ),
        apiRequest<EventPage>(
          `/api/v1/repair-sessions/${sessionId}/events?after_sequence=0&limit=100`,
          {},
          { retryIdempotent: true },
        ),
      ])
      setSelectedId(sessionId)
      setSnapshot(resume)
      setHistory(events.items)
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
      setMessage('Repair session started and saved to PartGraph.')
      await refreshLists()
      await loadSession(created.session.id)
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
      const result = await apiRequest<MutationResult>(
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
        setHistory([])
        setSelectedId(null)
        const rows = await refreshLists()
        if (rows[0]) await loadSession(rows[0].id)
      } else {
        setSnapshot({ ...snapshot!, session: result.session, last_event: result.event, lease: result.lease })
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
    return <p className="repair-loading">Loading your repair state…</p>
  }

  return (
    <div className="repair-workspace">
      <header className="repair-heading">
        <div>
          <p className="eyebrow">PARTGRAPH · RESUME</p>
          <h1>Return to the same repair state.</h1>
          <p className="lede">
            Repair sessions remember what PartGraph has actually recorded. Guidance, parts, and
            fasteners appear only after those verified domains exist.
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
            <>
              <div className="repair-current-head">
                <div>
                  <p className="eyebrow">CURRENT STATE · EVENT {snapshot.session.current_sequence}</p>
                  <h2>{snapshot.session.title}</h2>
                  <p>{vehicleName(snapshot.vehicle)}</p>
                </div>
                <span className={`repair-status repair-status--${snapshot.session.status}`}>{snapshot.session.status}</span>
              </div>

              <div className="repair-facts">
                <div>
                  <span>Last recorded event</span>
                  <strong>{eventLabel(snapshot.last_event)}</strong>
                  <small>{new Date(snapshot.last_event.created_at).toLocaleString()}</small>
                </div>
                <div>
                  <span>Editing control</span>
                  <strong>{snapshot.lease.status.replaceAll('_', ' ')}</strong>
                  <small>{snapshot.lease.can_edit ? 'This device may change state.' : 'Viewing is read-only.'}</small>
                </div>
                <div>
                  <span>Next verified action</span>
                  <strong>Not available yet</strong>
                  <small>A verified repair plan/dependency domain has not been implemented.</small>
                </div>
              </div>

              <div className="repair-actions">
                {snapshot.lease.status === 'available' && snapshot.session.status !== 'archived' && (
                  <button disabled={busy} onClick={() => void leaseAction(false)}>Take editing control</button>
                )}
                {snapshot.lease.status === 'held_by_other' && snapshot.session.status !== 'archived' && (
                  <button disabled={busy} onClick={() => void leaseAction(true)}>Take over session</button>
                )}
                {snapshot.lease.can_edit && snapshot.session.status === 'active' && (
                  <button disabled={busy} onClick={() => void stateAction('pause')}>Pause repair</button>
                )}
                {snapshot.lease.can_edit && snapshot.session.status === 'paused' && (
                  <button disabled={busy} onClick={() => void stateAction('resume')}>Resume work</button>
                )}
                {snapshot.lease.can_edit && snapshot.session.status !== 'archived' && (
                  <button className="secondary" disabled={busy} onClick={() => void stateAction('archive')}>Archive</button>
                )}
              </div>

              <section className="repair-history">
                <div className="repair-section-title">
                  <div>
                    <p className="eyebrow">IMMUTABLE HISTORY</p>
                    <h3>Recorded events</h3>
                  </div>
                  <span>{history.length}</span>
                </div>
                <ol>
                  {history.map((event) => (
                    <li key={event.id}>
                      <span>{event.sequence}</span>
                      <div>
                        <strong>{eventLabel(event)}</strong>
                        <small>{new Date(event.created_at).toLocaleString()}</small>
                      </div>
                    </li>
                  ))}
                </ol>
              </section>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
