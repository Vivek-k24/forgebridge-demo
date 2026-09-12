import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { activeRepairSessionId, setActiveRepairSessionId } from './active-repair'
import { apiRequest, formatApiFailure } from './api'
import {
  recoverableRepairSessionCreation,
  repairDeviceId,
  repairMutationHeaders,
} from './repair-client'
import './repair-workspaces.css'
import './start-repair.css'

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
}

type RepairSessionResume = {
  session: RepairSession
}

type RepairDefinitionOption = {
  repair_definition_id: string
  repair_key: string
  title: string
  version: number
}

type RepairDefinitionOptions = {
  session_id: string
  vehicle_resolution: 'exact' | 'unresolved'
  options: RepairDefinitionOption[]
}

function vehicleLabel(vehicle: UserVehicle): string {
  const identity = vehicle.identity
  const base = [identity.year, identity.make, identity.model, identity.trim]
    .filter(Boolean)
    .join(' ')
  return vehicle.nickname ? `${vehicle.nickname} · ${base}` : base
}

function vehicleTitle(vehicle: UserVehicle): string {
  return vehicle.nickname || [vehicle.identity.year, vehicle.identity.make, vehicle.identity.model]
    .filter(Boolean)
    .join(' ')
}

export function StartRepairWorkspace({
  preferredVehicleId,
  onOpenGarage,
  onCreated,
}: {
  preferredVehicleId: string
  onOpenGarage: () => void
  onCreated: (sessionId: string) => void
}) {
  const [vehicles, setVehicles] = useState<UserVehicle[]>([])
  const [selectedVehicleId, setSelectedVehicleId] = useState(preferredVehicleId || '')
  const [title, setTitle] = useState('')
  const [pendingSession, setPendingSession] = useState<RepairSession | null>(null)
  const [repairOptions, setRepairOptions] = useState<RepairDefinitionOption[]>([])
  const [selectedRepairKey, setSelectedRepairKey] = useState('')
  const [vehicleResolution, setVehicleResolution] = useState<'exact' | 'unresolved' | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedVehicle = useMemo(
    () => vehicles.find((vehicle) => vehicle.id === selectedVehicleId) || null,
    [vehicles, selectedVehicleId],
  )

  useEffect(() => {
    let active = true

    async function load() {
      try {
        setLoading(true)
        const rows = await apiRequest<UserVehicle[]>('/api/v1/user-vehicles', undefined, {
          retryIdempotent: true,
        })
        if (!active) return
        const available = rows.filter((vehicle) => !vehicle.archived_at)
        setVehicles(available)
        setSelectedVehicleId((current) => {
          if (preferredVehicleId && available.some((vehicle) => vehicle.id === preferredVehicleId)) {
            return preferredVehicleId
          }
          if (current && available.some((vehicle) => vehicle.id === current)) return current
          return available[0]?.id || ''
        })
      } catch (failure) {
        if (active) setError(formatApiFailure(failure, 'Could not load your garage.'))
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [preferredVehicleId])

  function finish(sessionId: string) {
    setActiveRepairSessionId(sessionId)
    window.dispatchEvent(new CustomEvent('partgraph:repair-sessions-changed'))
    onCreated(sessionId)
  }

  async function createRepair(event: FormEvent) {
    event.preventDefault()
    if (!selectedVehicleId || !title.trim()) return

    try {
      setBusy(true)
      setError(null)
      setPendingSession(null)
      setRepairOptions([])
      setSelectedRepairKey('')
      setVehicleResolution(null)

      const creation = await recoverableRepairSessionCreation<RepairSessionResume>(
        '/api/v1/repair-sessions',
        {
          method: 'POST',
          body: JSON.stringify({
            user_vehicle_id: selectedVehicleId,
            title: title.trim(),
          }),
        },
        { json: true, prefix: 'start_repair' },
      )
      const created = creation.kind === 'response'
        ? creation.value
        : await apiRequest<RepairSessionResume>(
            `/api/v1/repair-sessions/${creation.sessionId}/resume`,
            { headers: { 'X-PartGraph-Device-ID': repairDeviceId() } },
            { retryIdempotent: true },
          )
      const session = created.session
      setActiveRepairSessionId(session.id)
      window.dispatchEvent(new CustomEvent('partgraph:repair-sessions-changed'))

      try {
        const options = await apiRequest<RepairDefinitionOptions>(
          `/api/v1/repair-sessions/${session.id}/repair-options`,
          undefined,
          { retryIdempotent: true },
        )
        setVehicleResolution(options.vehicle_resolution)
        if (options.vehicle_resolution === 'exact' && options.options.length > 0) {
          setPendingSession(session)
          setRepairOptions(options.options)
          setSelectedRepairKey(options.options[0].repair_key)
          return
        }
      } catch (failure) {
        setPendingSession(session)
        setError(
          `${formatApiFailure(
            failure,
            'The repair session was created, but verified repair options could not be loaded.',
          )} You can continue and connect verified requirements later in Readiness.`,
        )
        return
      }

      finish(session.id)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not start this repair.'))
    } finally {
      setBusy(false)
    }
  }

  async function bindVerifiedRepair() {
    if (!pendingSession || !selectedRepairKey) return
    try {
      setBusy(true)
      setError(null)
      await apiRequest(`/api/v1/repair-sessions/${pendingSession.id}/repair-definition`, {
        method: 'PUT',
        headers: repairMutationHeaders({ json: true }),
        body: JSON.stringify({ repair_key: selectedRepairKey }),
      })
      finish(pendingSession.id)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not connect this verified repair.'))
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <main className="repair-workspace-shell start-repair-shell">
        <section className="repair-panel panel start-repair-loading">Loading your Garage…</section>
      </main>
    )
  }

  if (pendingSession) {
    return (
      <main className="repair-workspace-shell start-repair-shell">
        <header className="workspace-hero">
          <p className="eyebrow">PARTGRAPH · START REPAIR</p>
          <h1>Connect the repair to verified vehicle-specific guidance.</h1>
          <p>
            Your repair session is already saved. PartGraph only offers a verified repair option when
            the stored repair definition applies to this exact vehicle configuration.
          </p>
        </header>

        <div className="start-repair-steps" aria-label="Start repair progress">
          <span className="start-step start-step--done"><b>1</b> Vehicle</span>
          <span className="start-step start-step--done"><b>2</b> Session</span>
          <span className="start-step start-step--active"><b>3</b> Verified context</span>
        </div>

        {error && <div className="workspace-alert workspace-alert--error">{error}</div>}

        <section className="repair-panel panel start-context-panel">
          <div className="start-context-summary">
            <div>
              <p className="eyebrow">SAVED SESSION</p>
              <h2>{pendingSession.title}</h2>
              <p>{selectedVehicle ? vehicleLabel(selectedVehicle) : 'Saved Garage vehicle'}</p>
            </div>
            <span className="status-pill status-pill--ok">Session saved</span>
          </div>

          {repairOptions.length > 0 ? (
            <div className="start-verified-block">
              <div className="start-verified-heading">
                <div>
                  <p className="eyebrow">VERIFIED REPAIR OPTIONS</p>
                  <h3>Select the repair PartGraph should bind to this session.</h3>
                </div>
                <span>{repairOptions.length} available</span>
              </div>

              <label className="start-repair-select">
                <span>Verified repair</span>
                <select
                  value={selectedRepairKey}
                  disabled={busy}
                  onChange={(event) => setSelectedRepairKey(event.target.value)}
                >
                  {repairOptions.map((option) => (
                    <option key={option.repair_definition_id} value={option.repair_key}>
                      {option.title} · v{option.version}
                    </option>
                  ))}
                </select>
              </label>

              <div className="repair-button-row">
                <button
                  type="button"
                  disabled={busy || !selectedRepairKey}
                  onClick={() => void bindVerifiedRepair()}
                >
                  Use verified repair
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={() => finish(pendingSession.id)}
                >
                  Continue without guidance
                </button>
              </div>
              <p className="start-helper">
                A bound repair definition is version-pinned. Continuing without one keeps the session
                useful for observations, photos, and repair memory without inventing procedure data.
              </p>
            </div>
          ) : (
            <div className="repair-empty start-no-guidance">
              <h3>No verified repair guidance is available for this session yet.</h3>
              <p>
                {vehicleResolution === 'unresolved'
                  ? 'This saved vehicle is not resolved to one exact verified configuration.'
                  : 'PartGraph can still preserve the repair state without pretending a procedure exists.'}
              </p>
              <button type="button" disabled={busy} onClick={() => finish(pendingSession.id)}>
                Continue to repair workspace
              </button>
            </div>
          )}
        </section>
      </main>
    )
  }

  return (
    <main className="repair-workspace-shell start-repair-shell">
      <header className="workspace-hero repair-hero-row">
        <div>
          <p className="eyebrow">PARTGRAPH · START REPAIR</p>
          <h1>Choose the vehicle, then tell PartGraph what you are working on.</h1>
          <p>
            The repair session becomes the durable record for repair state, readiness, guidance,
            observations, photos, and physical-part memory.
          </p>
        </div>
        <button type="button" className="secondary" onClick={onOpenGarage}>Open Garage</button>
      </header>

      <div className="start-repair-steps" aria-label="Start repair progress">
        <span className="start-step start-step--active"><b>1</b> Vehicle</span>
        <span className="start-step"><b>2</b> Session</span>
        <span className="start-step"><b>3</b> Verified context</span>
      </div>

      {error && <div className="workspace-alert workspace-alert--error">{error}</div>}

      {vehicles.length === 0 ? (
        <section className="repair-empty panel start-repair-empty">
          <h2>Your Garage is empty.</h2>
          <p>Add a vehicle before starting a repair. PartGraph does not create a repair without vehicle context.</p>
          <button type="button" onClick={onOpenGarage}>Add vehicle</button>
        </section>
      ) : (
        <section className="start-repair-grid">
          <article className="repair-panel panel start-vehicle-card">
            <p className="eyebrow">SELECTED VEHICLE</p>
            {selectedVehicle ? (
              <>
                <h2>{vehicleTitle(selectedVehicle)}</h2>
                <p>{vehicleLabel(selectedVehicle)}</p>
                <dl>
                  <div><dt>Year</dt><dd>{selectedVehicle.identity.year}</dd></div>
                  <div><dt>Make</dt><dd>{selectedVehicle.identity.make}</dd></div>
                  <div><dt>Model</dt><dd>{selectedVehicle.identity.model}</dd></div>
                  <div><dt>Trim</dt><dd>{selectedVehicle.identity.trim || 'Not specified'}</dd></div>
                </dl>
              </>
            ) : (
              <p className="muted">Choose a vehicle to continue.</p>
            )}
          </article>

          <section className="repair-panel panel start-session-card">
            <form className="compact-form" onSubmit={(event) => void createRepair(event)}>
              <label>
                <span>Vehicle</span>
                <select
                  value={selectedVehicleId}
                  disabled={busy}
                  onChange={(event) => setSelectedVehicleId(event.target.value)}
                >
                  {vehicles.map((vehicle) => (
                    <option key={vehicle.id} value={vehicle.id}>{vehicleLabel(vehicle)}</option>
                  ))}
                </select>
              </label>

              <label>
                <span>Repair or problem</span>
                <input
                  value={title}
                  maxLength={160}
                  disabled={busy}
                  placeholder="Describe the repair or problem"
                  onChange={(event) => setTitle(event.target.value)}
                />
              </label>

              {activeRepairSessionId() && (
                <div className="start-existing-session">
                  <strong>You already have a repair available to resume.</strong>
                  <span>Starting this repair will make the new session the active workspace.</span>
                </div>
              )}

              <button disabled={busy || !selectedVehicleId || !title.trim()}>
                {busy ? 'Starting…' : 'Create repair session'}
              </button>
            </form>
          </section>
        </section>
      )}
    </main>
  )
}
