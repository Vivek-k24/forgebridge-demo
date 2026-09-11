import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiRequest, formatApiFailure } from './api'
import { activeRepairSessionId, setActiveRepairSessionId } from './active-repair'
import './home-workspace.css'

type UserVehicle = {
  id: string
  nickname: string | null
  archived_at: string | null
  identity: {
    year: number
    make: string
    model: string
    trim: string | null
  }
}

type RepairSession = {
  id: string
  user_vehicle_id: string
  title: string
  status: 'active' | 'paused' | 'archived'
  current_sequence: number
  archived_at: string | null
  created_at: string
  updated_at: string
}

type LoadState = 'loading' | 'ready' | 'error'

function vehicleLabel(vehicle: UserVehicle | undefined): string {
  if (!vehicle) return 'Vehicle unavailable'
  const identity = [
    vehicle.identity.year,
    vehicle.identity.make,
    vehicle.identity.model,
    vehicle.identity.trim,
  ].filter(Boolean).join(' ')
  return vehicle.nickname ? `${vehicle.nickname} · ${identity}` : identity
}

function statusLabel(status: RepairSession['status']): string {
  if (status === 'active') return 'In progress'
  if (status === 'paused') return 'Paused'
  return 'Archived'
}

function formatUpdatedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Update time unavailable'
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date)
}

export function HomeWorkspace({
  onOpenGarage,
  onStartRepair,
  onResumeRepair,
}: {
  onOpenGarage: () => void
  onStartRepair: () => void
  onResumeRepair: () => void
}) {
  const [vehicles, setVehicles] = useState<UserVehicle[]>([])
  const [sessions, setSessions] = useState<RepairSession[]>([])
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoadState('loading')
    setError(null)
    try {
      const [vehicleRows, sessionRows] = await Promise.all([
        apiRequest<UserVehicle[]>('/api/v1/user-vehicles', undefined, { retryIdempotent: true }),
        apiRequest<RepairSession[]>('/api/v1/repair-sessions?limit=50', undefined, {
          retryIdempotent: true,
        }),
      ])
      setVehicles(vehicleRows.filter((vehicle) => !vehicle.archived_at))
      setSessions(sessionRows.filter((session) => !session.archived_at))
      setLoadState('ready')
    } catch (failure) {
      setVehicles([])
      setSessions([])
      setError(formatApiFailure(failure, 'Could not load your PartGraph workspace.'))
      setLoadState('error')
    }
  }, [])

  useEffect(() => {
    void load()
    const refresh = () => void load()
    window.addEventListener('partgraph:repair-sessions-changed', refresh)
    return () => window.removeEventListener('partgraph:repair-sessions-changed', refresh)
  }, [load])

  const vehiclesById = useMemo(
    () => new Map(vehicles.map((vehicle) => [vehicle.id, vehicle])),
    [vehicles],
  )
  const activeCount = sessions.filter((session) => session.status === 'active').length
  const pausedCount = sessions.filter((session) => session.status === 'paused').length
  const recentSessions = useMemo(
    () => [...sessions].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at)).slice(0, 5),
    [sessions],
  )
  const currentSessionId = activeRepairSessionId()

  function continueSession(sessionId: string) {
    setActiveRepairSessionId(sessionId)
    onResumeRepair()
  }

  return (
    <main className="home-workspace">
      <header className="home-hero">
        <div>
          <p className="home-eyebrow">PARTGRAPH · OWNER WORKSPACE</p>
          <h1>Your vehicles and repairs, in one place.</h1>
          <p>
            Pick up an existing repair, start a new one, or open your Garage. Everything shown here comes from your saved PartGraph state.
          </p>
        </div>
        <div className="home-hero-actions">
          <button type="button" className="home-primary-action" onClick={onStartRepair}>Start a repair</button>
          <button type="button" className="home-secondary-action" onClick={onOpenGarage}>Open Garage</button>
        </div>
      </header>

      {error && (
        <section className="home-alert" role="alert">
          <div>
            <strong>Workspace unavailable</strong>
            <span>{error}</span>
          </div>
          <button type="button" onClick={() => void load()}>Try again</button>
        </section>
      )}

      <section className="home-metrics" aria-label="Workspace summary">
        <article>
          <span>Vehicles</span>
          <strong>{loadState === 'loading' ? '—' : vehicles.length}</strong>
          <small>saved in your Garage</small>
        </article>
        <article>
          <span>In progress</span>
          <strong>{loadState === 'loading' ? '—' : activeCount}</strong>
          <small>active repair sessions</small>
        </article>
        <article>
          <span>Paused</span>
          <strong>{loadState === 'loading' ? '—' : pausedCount}</strong>
          <small>ready to resume later</small>
        </article>
      </section>

      <div className="home-grid">
        <section className="home-panel home-repairs-panel">
          <div className="home-section-heading">
            <div>
              <p className="home-eyebrow">RECENT REPAIRS</p>
              <h2>Continue where you left off.</h2>
            </div>
            {sessions.length > 0 && (
              <button type="button" className="home-text-action" onClick={onResumeRepair}>Open repair workspace</button>
            )}
          </div>

          {loadState === 'loading' ? (
            <div className="home-loading">Loading repair sessions…</div>
          ) : recentSessions.length === 0 ? (
            <div className="home-empty-state">
              <strong>No repair sessions yet.</strong>
              <p>Start a repair from a vehicle in your Garage when you are ready.</p>
              <button type="button" onClick={onStartRepair}>Start first repair</button>
            </div>
          ) : (
            <div className="home-repair-list">
              {recentSessions.map((session) => (
                <article
                  key={session.id}
                  className={session.id === currentSessionId ? 'home-repair-row home-repair-row--current' : 'home-repair-row'}
                >
                  <div className="home-repair-main">
                    <div className="home-repair-status-line">
                      <span className={`home-status home-status--${session.status}`}>{statusLabel(session.status)}</span>
                      {session.id === currentSessionId && <span className="home-current-label">Current</span>}
                    </div>
                    <h3>{session.title}</h3>
                    <p>{vehicleLabel(vehiclesById.get(session.user_vehicle_id))}</p>
                  </div>
                  <div className="home-repair-meta">
                    <span>event {session.current_sequence}</span>
                    <span>{formatUpdatedAt(session.updated_at)}</span>
                    <button type="button" onClick={() => continueSession(session.id)}>Continue</button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <aside className="home-side-column">
          <section className="home-panel home-next-panel">
            <p className="home-eyebrow">WHAT DO YOU WANT TO DO?</p>
            <div className="home-action-stack">
              <button type="button" onClick={onOpenGarage}>
                <strong>Manage vehicles</strong>
                <span>Add a vehicle, review identity, or start from your Garage.</span>
              </button>
              <button type="button" onClick={onStartRepair}>
                <strong>Start a repair</strong>
                <span>Create a repair session for one of your saved vehicles.</span>
              </button>
              <button type="button" onClick={onResumeRepair} disabled={sessions.length === 0}>
                <strong>Resume repair work</strong>
                <span>Return to saved physical state, readiness, guidance, and history.</span>
              </button>
            </div>
          </section>

          <section className="home-panel home-trust-panel">
            <p className="home-eyebrow">PARTGRAPH BEHAVIOR</p>
            <h2>Missing information stays missing.</h2>
            <p>
              PartGraph keeps verified automotive knowledge separate from your private repair state and does not fill gaps with invented mechanical facts.
            </p>
          </section>
        </aside>
      </div>
    </main>
  )
}
