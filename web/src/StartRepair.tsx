import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { apiRequest, formatApiFailure } from './api'
import { repairMutationHeaders } from './repair-client'
import './repair-workspaces.css'

type UserVehicle = {
  id: string
  nickname: string | null
  canonical_configuration_id: string | null
  identity_resolution: 'matched' | 'ambiguous' | 'manual_candidate'
  identity: {
    year: number
    make: string
    model: string
    trim: string | null
    engine: string | null
    transmission: string | null
  }
  archived_at: string | null
}
type RepairSession = {
  id: string
  user_vehicle_id: string
  title: string
  status: 'active' | 'paused' | 'archived'
  current_sequence: number
}

function vehicleLabel(vehicle: UserVehicle) {
  return vehicle.nickname || [vehicle.identity.year, vehicle.identity.make, vehicle.identity.model, vehicle.identity.trim].filter(Boolean).join(' ')
}

export function StartRepairWorkspace({
  preferredVehicleId,
  onOpenGarage,
  onCreated,
}: {
  preferredVehicleId?: string | null
  onOpenGarage: () => void
  onCreated: (sessionId: string) => void
}) {
  const [vehicles, setVehicles] = useState<UserVehicle[]>([])
  const [selectedVehicleId, setSelectedVehicleId] = useState(preferredVehicleId || '')
  const [title, setTitle] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    apiRequest<UserVehicle[]>('/api/v1/user-vehicles', undefined, { retryIdempotent: true })
      .then((rows) => {
        if (!active) return
        const available = rows.filter((row) => !row.archived_at)
        setVehicles(available)
        setSelectedVehicleId((current) => {
          if (preferredVehicleId && available.some((vehicle) => vehicle.id === preferredVehicleId)) return preferredVehicleId
          if (current && available.some((vehicle) => vehicle.id === current)) return current
          return available[0]?.id || ''
        })
      })
      .catch((failure) => { if (active) setError(formatApiFailure(failure, 'Could not load your garage.')) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [preferredVehicleId])

  const selectedVehicle = useMemo(
    () => vehicles.find((vehicle) => vehicle.id === selectedVehicleId) || null,
    [vehicles, selectedVehicleId],
  )

  async function createRepair(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!selectedVehicleId) {
      setError('Choose a garage vehicle before starting a repair.')
      return
    }
    if (!title.trim()) {
      setError('Give this repair a short title so it can be resumed later.')
      return
    }
    setSaving(true)
    try {
      const created = await apiRequest<RepairSession>('/api/v1/repair-sessions', {
        method: 'POST',
        headers: repairMutationHeaders({ json: true }),
        body: JSON.stringify({ user_vehicle_id: selectedVehicleId, title: title.trim() }),
      })
      window.sessionStorage.setItem('partgraph:active-repair-session', created.id)
      window.dispatchEvent(new CustomEvent('partgraph:repair-sessions-changed'))
      onCreated(created.id)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not start this repair session.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="repair-workspace-shell">
      <header className="workspace-hero">
        <p className="eyebrow">PARTGRAPH · START REPAIR</p>
        <h1>Start a repair from a vehicle already in your garage.</h1>
        <p>The session becomes the durable repair timeline for readiness, verified guidance, fasteners, observations, evidence, inventory, and resume continuity.</p>
      </header>

      <section className="repair-panel panel">
        {loading && <p className="muted">Loading your garage…</p>}
        {!loading && vehicles.length === 0 && (
          <div className="repair-empty">
            <h2>Add a vehicle first</h2>
            <p>A repair session must belong to a private garage vehicle so PartGraph can bind the correct canonical identity and keep owner data isolated.</p>
            <button type="button" onClick={onOpenGarage}>Open Garage</button>
          </div>
        )}
        {!loading && vehicles.length > 0 && (
          <form className="start-repair-form" onSubmit={(event) => void createRepair(event)}>
            <label>
              <span>Vehicle</span>
              <select value={selectedVehicleId} onChange={(event) => setSelectedVehicleId(event.target.value)}>
                {vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicleLabel(vehicle)}</option>)}
              </select>
            </label>
            {selectedVehicle && (
              <div className="repair-context-card">
                <strong>{vehicleLabel(selectedVehicle)}</strong>
                <span>{selectedVehicle.identity.engine || 'Engine not yet resolved'} · {selectedVehicle.identity.transmission || 'Transmission not yet resolved'}</span>
                <span>{selectedVehicle.canonical_configuration_id ? 'Canonical configuration linked' : 'Private identity only'} · {selectedVehicle.identity_resolution.replace('_', ' ')}</span>
              </div>
            )}
            <label>
              <span>Repair title</span>
              <input maxLength={160} value={title} placeholder="Replace radiator support, diagnose idle surge…" onChange={(event) => setTitle(event.target.value)} />
            </label>
            <button type="submit" disabled={saving}>{saving ? 'Starting repair…' : 'Start repair'}</button>
          </form>
        )}
        {error && <div className="workspace-alert workspace-alert--error">{error}</div>}
      </section>
    </main>
  )
}
