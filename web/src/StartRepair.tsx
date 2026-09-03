import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { activeRepairSessionId, setActiveRepairSessionId } from './active-repair'
import { apiRequest, formatApiFailure } from './api'
import { repairMutationHeaders } from './repair-client'
import './repair-workspaces.css'

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

      const created = await apiRequest<RepairSessionResume>('/api/v1/repair-sessions', {
        method: 'POST',
        headers: repairMutationHeaders({ json: true }),
        body: JSON.stringify({ user_vehicle_id: selectedVehicleId, title: title.trim() }),
      })
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
          `${formatApiFailure(failure, 'The repair session was created, but verified repair options could not be loaded.')} You can continue and connect verified requirements later in Readiness.`,
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

  if (loading) return <section className="repair-panel panel"><p>Loading garage…</p></section>

  if (pendingSession) {
    return (
      <main className="repair-workspace-shell">
        <header className="workspace-hero">
          <p className="eyebrow">PARTGRAPH · START REPAIR</p>
          <h1>Choose the verified repair context.</h1>
          <p>
            The repair session is already saved. When PartGraph has verified repair definitions for
            this exact vehicle, bind one now so Readiness and Guided Repair start with the correct
            requirements and procedure context.
          </p>
        </header>

        {error && <div className="workspace-alert workspace-alert--error">{error}</div>}

        <section className="repair-panel panel">
          <p className="eyebrow">SESSION CREATED</p>
          <h2>{pendingSession.title}</h2>
          <p>{selectedVehicle ? vehicleLabel(selectedVehicle) : 'Saved garage vehicle'}</p>

          {repairOptions.length > 0 ? (
            <div className="compact-form">
              <label>
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
                <button type="button" disabled={busy || !selectedRepairKey} onClick={() => void bindVerifiedRepair()}>
                  Use verified repair
                </button>
                <button type="button" className="secondary" disabled={busy} onClick={() => finish(pendingSession.id)}>
                  Continue without binding
                </button>
              </div>
              <small>
                Binding is version-pinned and cannot be silently switched later. Continue without
                binding only for diagnosis or work that does not yet have verified PartGraph repair truth.
              </small>
            </div>
          ) : (
            <div className="repair-empty">
              <h3>No verified repair option loaded.</h3>
              <p>
                {vehicleResolution === 'unresolved'
                  ? 'This garage vehicle is not resolved to an exact canonical configuration.'
                  : 'The session can still be used for diagnosis, observations, photos, and repair memory.'}
              </p>
              <button type="button" disabled={busy} onClick={() => finish(pendingSession.id)}>
                Continue to repair
              </button>
            </div>
          )}
        </section>
      </main>
    )
  }

  return (
    <main className="repair-workspace-shell">
      <header className="workspace-hero repair-hero-row">
        <div>
          <p className="eyebrow">PARTGRAPH · START REPAIR</p>
          <h1>Start from a vehicle already in your Garage.</h1>
          <p>
            The Repair Session becomes the durable repair record for progress, inventory, guidance,
            observations, photos, and physical-part memory.
          </p>
        </div>
        <button type="button" className="secondary" onClick={onOpenGarage}>Open Garage</button>
      </header>

      {error && <div className="workspace-alert workspace-alert--error">{error}</div>}

      {vehicles.length === 0 ? (
        <section className="repair-empty panel">
          <h2>Your Garage is empty.</h2>
          <p>Add a vehicle manually or by VIN before starting a repair.</p>
          <button type="button" onClick={onOpenGarage}>Add vehicle</button>
        </section>
      ) : (
        <section className="repair-panel panel">
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
              <span>What are you working on?</span>
              <input
                value={title}
                maxLength={160}
                disabled={busy}
                placeholder="Radiator replacement, diagnose rough idle…"
                onChange={(event) => setTitle(event.target.value)}
              />
            </label>
            {activeRepairSessionId() && (
              <small>A previous repair remains available under Resume. Starting this one will make it the active repair across workspaces.</small>
            )}
            <button disabled={busy || !selectedVehicleId || !title.trim()}>
              {busy ? 'Starting…' : 'Start repair'}
            </button>
          </form>
        </section>
      )}
    </main>
  )
}
