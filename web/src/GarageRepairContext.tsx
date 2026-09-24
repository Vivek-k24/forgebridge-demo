import { useCallback, useEffect, useMemo, useState } from 'react'
import { activeRepairSessionId, preferredRepairSessionId, setActiveRepairSessionId } from './active-repair'
import { apiRequest, CSRF_HEADERS, formatApiFailure } from './api'
import { partGraphDeviceId } from './device'
import './garage-repair-context.css'

type LeaseStatus = 'available' | 'owned' | 'held_by_other'
type RepairSession = {
  id: string
  title: string
  status: 'active' | 'paused' | 'archived'
  current_sequence: number
}
type ResumeSnapshot = {
  session: RepairSession
  vehicle: {
    nickname: string | null
    identity: { year: number; make: string; model: string; trim: string | null }
  }
  lease: { status: LeaseStatus; can_edit: boolean; expires_at: string | null }
}

function vehicleLabel(snapshot: ResumeSnapshot) {
  const identity = snapshot.vehicle.identity
  const base = [identity.year, identity.make, identity.model, identity.trim].filter(Boolean).join(' ')
  return snapshot.vehicle.nickname ? `${snapshot.vehicle.nickname} · ${base}` : base
}

function statusLabel(status: RepairSession['status']) {
  if (status === 'active') return 'Active repair'
  if (status === 'paused') return 'Paused repair'
  return 'Archived repair'
}

export function GarageRepairContext() {
  const deviceId = useMemo(() => partGraphDeviceId(), [])
  const [sessions, setSessions] = useState<RepairSession[]>([])
  const [sessionId, setSessionId] = useState(() => activeRepairSessionId() || '')
  const [snapshot, setSnapshot] = useState<ResumeSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSnapshot = useCallback(async (selectedSessionId: string) => {
    if (!selectedSessionId) {
      setSnapshot(null)
      setActiveRepairSessionId(null)
      return
    }
    const resume = await apiRequest<ResumeSnapshot>(
      `/api/v1/repair-sessions/${selectedSessionId}/resume`,
      { headers: { 'X-PartGraph-Device-ID': deviceId } },
      { retryIdempotent: true },
    )
    setSnapshot(resume)
    setActiveRepairSessionId(selectedSessionId)
  }, [deviceId])

  useEffect(() => {
    let active = true
    async function initialize() {
      try {
        setLoading(true)
        setError(null)
        const rows = await apiRequest<RepairSession[]>('/api/v1/repair-sessions')
        if (!active) return
        setSessions(rows)
        const selected = preferredRepairSessionId(rows, sessionId)
        setSessionId(selected)
        await loadSnapshot(selected)
      } catch (failure) {
        if (active) setError(formatApiFailure(failure, 'Could not load current repair.'))
      } finally {
        if (active) setLoading(false)
      }
    }
    void initialize()
    return () => { active = false }
  }, [loadSnapshot, sessionId])

  async function selectSession(nextSessionId: string) {
    try {
      setError(null)
      setSessionId(nextSessionId)
      setActiveRepairSessionId(nextSessionId || null)
      setSnapshot(null)
      await loadSnapshot(nextSessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not switch repairs.'))
    }
  }

  async function acquireLease(takeover: boolean) {
    if (!sessionId) return
    try {
      setBusy(true)
      setError(null)
      await apiRequest(`/api/v1/repair-sessions/${sessionId}/lease/${takeover ? 'takeover' : 'acquire'}`, {
        method: 'POST',
        headers: { ...CSRF_HEADERS, 'X-PartGraph-Device-ID': deviceId },
      })
      await loadSnapshot(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not enable editing on this device.'))
    } finally {
      setBusy(false)
    }
  }

  if (loading) return null
  if (sessions.length === 0) return null

  const canEdit = snapshot?.lease.can_edit ?? false

  return (
    <section className="garage-repair-context-shell" aria-label="Current repair">
      <div className="garage-repair-context">
        <label>
          <span>Current repair</span>
          <select value={sessionId} onChange={(event) => void selectSession(event.target.value)}>
            {sessions.map((item) => <option key={item.id} value={item.id}>{item.title} · {item.status}</option>)}
          </select>
        </label>
        {snapshot && (
          <div className="garage-repair-context__vehicle">
            <strong>{vehicleLabel(snapshot)}</strong>
            <span>{statusLabel(snapshot.session.status)} · {canEdit ? 'Editing here' : 'View only'}</span>
          </div>
        )}
        {snapshot && !canEdit && snapshot.session.status !== 'archived' && (
          <button type="button" disabled={busy} onClick={() => void acquireLease(snapshot.lease.status === 'held_by_other')}>
            {snapshot.lease.status === 'held_by_other' ? 'Move editing here' : 'Edit this repair'}
          </button>
        )}
      </div>
      {error && <p className="garage-repair-context__error">{error}</p>}
    </section>
  )
}
