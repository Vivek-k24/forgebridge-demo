import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { activeRepairSessionId, preferredRepairSessionId, setActiveRepairSessionId } from './active-repair'
import { apiRequest, CSRF_HEADERS, formatApiFailure } from './api'
import { newIdempotencyKey, partGraphDeviceId } from './device'
import './repair-memory.css'

type LeaseStatus = 'available' | 'owned' | 'held_by_other'
type ProcurementState = 'needed' | 'ordered' | 'available' | 'unavailable'
type ReadinessState = 'have' | 'missing' | 'ordered' | 'unavailable'
type ReadinessSource = 'session' | 'garage' | 'existing_vehicle' | 'default'

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

type InventoryItem = {
  id: string
  session_id: string
  name: string
  quantity: number
  procurement_state: ProcurementState
  reference: string | null
  notes: string | null
  created_at: string
  updated_at: string
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

type RepairReadinessItem = {
  requirement_definition_id: string
  requirement_key: string
  category: string
  display_name: string
  required_quantity: string | null
  unit: string | null
  necessity: string
  fulfillment_mode: string
  operation_keys: string[]
  quantity_available: string
  readiness_state: ReadinessState
  readiness_source: ReadinessSource
  procurement_reference: string | null
  notes: string | null
}

type RepairReadiness = {
  session_id: string
  binding_status: 'unbound' | 'bound'
  repair: {
    repair_definition_id: string
    repair_key: string
    title: string
    version: number
    definition_status: 'verified' | 'superseded'
  } | null
  summary: {
    total: number
    ready: number
    missing: number
    ordered: number
    unavailable: number
    blocked: number
  }
  requirements: RepairReadinessItem[]
}

const PROCUREMENT_STATES: ProcurementState[] = ['needed', 'ordered', 'available', 'unavailable']
const READINESS_STATES: ReadinessState[] = ['have', 'missing', 'ordered', 'unavailable']

function jsonHeaders(deviceId: string, prefix: string): Record<string, string> {
  return {
    ...CSRF_HEADERS,
    'Content-Type': 'application/json',
    'X-PartGraph-Device-ID': deviceId,
    'Idempotency-Key': newIdempotencyKey(prefix),
  }
}

function vehicleLabel(snapshot: ResumeSnapshot | null): string {
  if (!snapshot) return ''
  const identity = snapshot.vehicle.identity
  const base = [identity.year, identity.make, identity.model, identity.trim].filter(Boolean).join(' ')
  return snapshot.vehicle.nickname ? `${snapshot.vehicle.nickname} · ${base}` : base
}

function procurementLabel(state: ProcurementState): string {
  switch (state) {
    case 'available': return 'Have it'
    case 'ordered': return 'Ordered'
    case 'unavailable': return 'Cannot get yet'
    default: return 'Need it'
  }
}

function readinessLabel(state: ReadinessState): string {
  switch (state) {
    case 'have': return 'Have it'
    case 'ordered': return 'Ordered'
    case 'unavailable': return 'Cannot get yet'
    default: return 'Need it'
  }
}

function readinessSourceLabel(source: ReadinessSource): string {
  switch (source) {
    case 'garage': return 'Already in your Garage'
    case 'existing_vehicle': return 'Already on the vehicle'
    case 'session': return 'Confirmed for this repair'
    default: return 'Not confirmed yet'
  }
}

function requirementQuantity(item: RepairReadinessItem): string {
  if (item.required_quantity === null) return 'Quantity not established'
  return `Need ${item.required_quantity}${item.unit ? ` ${item.unit}` : ''}`
}

function sessionStatusLabel(status: RepairSession['status']): string {
  if (status === 'active') return 'Active repair'
  if (status === 'paused') return 'Paused repair'
  return 'Archived repair'
}

export function RepairMemoryWorkspace() {
  const deviceId = useMemo(() => partGraphDeviceId(), [])
  const [sessions, setSessions] = useState<RepairSession[]>([])
  const [sessionId, setSessionId] = useState(() => activeRepairSessionId() || '')
  const [snapshot, setSnapshot] = useState<ResumeSnapshot | null>(null)
  const [inventory, setInventory] = useState<InventoryItem[]>([])
  const [readiness, setReadiness] = useState<RepairReadiness | null>(null)
  const [repairOptions, setRepairOptions] = useState<RepairDefinitionOptions | null>(null)
  const [selectedRepairKey, setSelectedRepairKey] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [inventoryName, setInventoryName] = useState('')
  const [inventoryQuantity, setInventoryQuantity] = useState(1)
  const [inventoryState, setInventoryState] = useState<ProcurementState>('needed')
  const [inventoryReference, setInventoryReference] = useState('')

  const loadReadiness = useCallback(async (selectedSessionId: string) => {
    if (!selectedSessionId) {
      setSnapshot(null)
      setInventory([])
      setReadiness(null)
      setRepairOptions(null)
      setSelectedRepairKey('')
      setActiveRepairSessionId(null)
      return
    }
    const [resume, inventoryRows, verifiedReadiness, options] = await Promise.all([
      apiRequest<ResumeSnapshot>(
        `/api/v1/repair-sessions/${selectedSessionId}/resume`,
        { headers: { 'X-PartGraph-Device-ID': deviceId } },
        { retryIdempotent: true },
      ),
      apiRequest<InventoryItem[]>(`/api/v1/repair-sessions/${selectedSessionId}/inventory`),
      apiRequest<RepairReadiness>(
        `/api/v1/repair-sessions/${selectedSessionId}/readiness`,
        undefined,
        { retryIdempotent: true },
      ),
      apiRequest<RepairDefinitionOptions>(
        `/api/v1/repair-sessions/${selectedSessionId}/repair-options`,
        undefined,
        { retryIdempotent: true },
      ),
    ])
    setSnapshot(resume)
    setInventory(inventoryRows)
    setReadiness(verifiedReadiness)
    setRepairOptions(options)
    setActiveRepairSessionId(selectedSessionId)
    setSelectedRepairKey((current) => {
      if (options.options.some((option) => option.repair_key === current)) return current
      return options.options[0]?.repair_key ?? ''
    })
  }, [deviceId])

  useEffect(() => {
    let active = true

    async function initialize() {
      try {
        setLoading(true)
        const rows = await apiRequest<RepairSession[]>('/api/v1/repair-sessions')
        if (!active) return
        setSessions(rows)
        const selected = preferredRepairSessionId(rows, sessionId)
        setSessionId(selected)
        await loadReadiness(selected)
      } catch (failure) {
        if (active) setError(formatApiFailure(failure, 'Could not load repair readiness.'))
      } finally {
        if (active) setLoading(false)
      }
    }

    void initialize()
    return () => { active = false }
  }, [loadReadiness, sessionId])

  async function selectSession(nextSessionId: string) {
    setSessionId(nextSessionId)
    setActiveRepairSessionId(nextSessionId || null)
    setSnapshot(null)
    setInventory([])
    setReadiness(null)
    setRepairOptions(null)
    setSelectedRepairKey('')
    setError(null)
    setMessage(null)
    await loadReadiness(nextSessionId)
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
      setMessage(takeover ? 'Editing moved to this device.' : 'You can now update this repair here.')
      await loadReadiness(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not enable editing on this device.'))
    } finally {
      setBusy(false)
    }
  }

  async function bindVerifiedRepair() {
    if (!sessionId || !selectedRepairKey) return
    try {
      setBusy(true)
      setError(null)
      await apiRequest(`/api/v1/repair-sessions/${sessionId}/repair-definition`, {
        method: 'PUT',
        headers: {
          ...CSRF_HEADERS,
          'Content-Type': 'application/json',
          'X-PartGraph-Device-ID': deviceId,
        },
        body: JSON.stringify({ repair_key: selectedRepairKey }),
      })
      setMessage('Verified repair requirements are now connected to this repair.')
      await loadReadiness(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not connect verified requirements.'))
    } finally {
      setBusy(false)
    }
  }

  async function changeVerifiedReadiness(item: RepairReadinessItem, state: ReadinessState) {
    if (!sessionId) return
    try {
      setBusy(true)
      setError(null)
      const updated = await apiRequest<RepairReadiness>(
        `/api/v1/repair-sessions/${sessionId}/readiness/${item.requirement_definition_id}`,
        {
          method: 'PUT',
          headers: jsonHeaders(deviceId, 'verified_readiness'),
          body: JSON.stringify({ readiness_state: state }),
        },
      )
      setReadiness(updated)
      setMessage(`${item.display_name}: ${readinessLabel(state)}.`)
      const resume = await apiRequest<ResumeSnapshot>(
        `/api/v1/repair-sessions/${sessionId}/resume`,
        { headers: { 'X-PartGraph-Device-ID': deviceId } },
        { retryIdempotent: true },
      )
      setSnapshot(resume)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not update repair readiness.'))
    } finally {
      setBusy(false)
    }
  }

  async function createInventory(event: FormEvent) {
    event.preventDefault()
    if (!sessionId || !inventoryName.trim()) return
    try {
      setBusy(true)
      setError(null)
      await apiRequest(`/api/v1/repair-sessions/${sessionId}/inventory`, {
        method: 'POST',
        headers: jsonHeaders(deviceId, 'readiness_inventory'),
        body: JSON.stringify({
          name: inventoryName.trim(),
          quantity: inventoryQuantity,
          procurement_state: inventoryState,
          reference: inventoryReference.trim() || null,
        }),
      })
      setInventoryName('')
      setInventoryQuantity(1)
      setInventoryState('needed')
      setInventoryReference('')
      setMessage('Item added to this repair.')
      await loadReadiness(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not add this item.'))
    } finally {
      setBusy(false)
    }
  }

  async function changeInventoryState(item: InventoryItem, state: ProcurementState) {
    if (!sessionId) return
    try {
      setBusy(true)
      setError(null)
      await apiRequest(`/api/v1/repair-sessions/${sessionId}/inventory/${item.id}`, {
        method: 'PATCH',
        headers: jsonHeaders(deviceId, 'readiness_inventory_state'),
        body: JSON.stringify({ procurement_state: state, quantity: item.quantity, notes: item.notes }),
      })
      setMessage(`${item.name}: ${procurementLabel(state)}.`)
      await loadReadiness(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not update this item.'))
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <p className="memory-loading">Loading repair readiness…</p>

  const canEdit = snapshot?.lease.can_edit ?? false
  const verifiedBound = readiness?.binding_status === 'bound'
  const manualAvailableCount = inventory.filter((item) => item.procurement_state === 'available').length
  const manualOrderedCount = inventory.filter((item) => item.procurement_state === 'ordered').length
  const manualMissingCount = inventory.filter((item) => item.procurement_state === 'needed' || item.procurement_state === 'unavailable').length
  const readinessPercent = readiness && readiness.summary.total > 0
    ? Math.round((readiness.summary.ready / readiness.summary.total) * 100)
    : 0

  return (
    <main className="memory-shell">
      <header className="memory-heading">
        <div>
          <p className="eyebrow">PARTGRAPH · READINESS</p>
          <h1>Get the repair ready before you start taking things apart.</h1>
          <p className="lede">See what this repair needs, confirm what you already have, and identify anything that could stop the job halfway through.</p>
        </div>
      </header>

      {error && <div className="memory-alert memory-alert--error">{error}</div>}
      {message && <div className="memory-alert memory-alert--success">{message}</div>}

      <section className="memory-session-bar panel">
        <label>
          <span>Repair</span>
          <select value={sessionId} onChange={(event) => void selectSession(event.target.value)}>
            {sessions.length === 0 && <option value="">No repair sessions</option>}
            {sessions.map((item) => <option key={item.id} value={item.id}>{item.title} · {item.status}</option>)}
          </select>
        </label>
        {snapshot && (
          <div className="memory-session-state">
            <strong>{vehicleLabel(snapshot)}</strong>
            <span>{sessionStatusLabel(snapshot.session.status)} · {canEdit ? 'Editing here' : 'View only'}</span>
          </div>
        )}
        {snapshot && !canEdit && snapshot.session.status !== 'archived' && (
          <button type="button" disabled={busy} onClick={() => void acquireLease(snapshot.lease.status === 'held_by_other')}>
            {snapshot.lease.status === 'held_by_other' ? 'Move editing here' : 'Edit this repair'}
          </button>
        )}
      </section>

      {!snapshot ? (
        <section className="memory-empty panel"><h2>No repair selected.</h2><p>Start or resume a repair before checking readiness.</p></section>
      ) : (
        <div className="memory-grid">
          {!verifiedBound && (
            <section className="panel memory-list-panel memory-span-all">
              <div className="memory-section-title"><div><p className="eyebrow">REPAIR SETUP</p><h2>Choose the verified repair when one is available.</h2></div></div>
              {repairOptions?.vehicle_resolution === 'unresolved' ? (
                <p className="memory-muted">PartGraph does not yet have an exact verified vehicle match for this saved vehicle, so it will not guess the repair requirements.</p>
              ) : repairOptions && repairOptions.options.length > 0 ? (
                <div className="memory-two-col">
                  <label><span>Verified repair</span><select value={selectedRepairKey} disabled={busy} onChange={(event) => setSelectedRepairKey(event.target.value)}>{repairOptions.options.map((option) => <option key={option.repair_definition_id} value={option.repair_key}>{option.title}</option>)}</select></label>
                  <button type="button" disabled={busy || !canEdit || !selectedRepairKey} onClick={() => void bindVerifiedRepair()}>Use these requirements</button>
                </div>
              ) : <p className="memory-muted">Verified requirements are not available for this repair yet. You can still track the items you need below.</p>}
            </section>
          )}

          {verifiedBound && readiness && (
            <>
              <section className="panel memory-list-panel memory-span-all">
                <div className="memory-section-title">
                  <div><p className="eyebrow">REPAIR READINESS</p><h2>{readiness.repair?.title}</h2><p className="memory-muted">Confirm each requirement before beginning the guided work.</p></div>
                  <strong className="memory-readiness-score">{readinessPercent}% ready</strong>
                </div>
                <div className="memory-progress" aria-label={`${readinessPercent}% of repair requirements ready`}>
                  <span style={{ width: `${readinessPercent}%` }} />
                </div>
                <div className="memory-chip-list"><span>{readiness.summary.ready} have</span><span>{readiness.summary.missing} need</span><span>{readiness.summary.ordered} ordered</span><span>{readiness.summary.unavailable} unavailable</span>{readiness.summary.blocked > 0 && <span>{readiness.summary.blocked} blocking</span>}</div>
              </section>

              <section className="panel memory-list-panel memory-span-all">
                <div className="memory-section-title"><div><p className="eyebrow">CHECKLIST</p><h2>What this repair needs</h2></div><span>{readiness.requirements.length}</span></div>
                <div className="memory-card-grid">
                  {readiness.requirements.map((item) => (
                    <article className={`memory-card memory-card--${item.readiness_state}`} key={item.requirement_definition_id}>
                      <div><strong>{item.display_name}</strong><span>{item.category.replaceAll('_', ' ')} · {requirementQuantity(item)}</span><span>{readinessSourceLabel(item.readiness_source)}</span></div>
                      <label><span>Status</span><select value={item.readiness_state} disabled={!canEdit || busy} onChange={(event) => void changeVerifiedReadiness(item, event.target.value as ReadinessState)}>{READINESS_STATES.map((state) => <option key={state} value={state}>{readinessLabel(state)}</option>)}</select></label>
                    </article>
                  ))}
                </div>
              </section>
            </>
          )}

          <section className="panel memory-list-panel">
            <div className="memory-section-title"><div><p className="eyebrow">EXTRA ITEMS</p><h2>Items you added</h2></div><span>{inventory.length}</span></div>
            <p className="memory-muted">Keep anything you discover during the job here when it is not already in the verified checklist.</p>
            <div className="memory-chip-list"><span>{manualAvailableCount} have</span><span>{manualOrderedCount} ordered</span><span>{manualMissingCount} need</span></div>
            <div className="memory-card-grid">
              {inventory.map((item) => (
                <article className="memory-card" key={item.id}>
                  <div><strong>{item.name}</strong><span>Quantity {item.quantity}{item.reference ? ` · ${item.reference}` : ''}</span></div>
                  <label><span>Status</span><select value={item.procurement_state} disabled={!canEdit || busy} onChange={(event) => void changeInventoryState(item, event.target.value as ProcurementState)}>{PROCUREMENT_STATES.map((state) => <option key={state} value={state}>{procurementLabel(state)}</option>)}</select></label>
                </article>
              ))}
              {inventory.length === 0 && <p className="memory-muted">Nothing extra has been added.</p>}
            </div>
          </section>

          <section className="panel memory-form-panel">
            <p className="eyebrow">ADD ITEM</p>
            <h2>Add something else you need for this repair.</h2>
            <p className="memory-muted">This stays with this repair and does not become shared vehicle data.</p>
            <form onSubmit={createInventory}>
              <label><span>Item</span><input value={inventoryName} maxLength={160} onChange={(event) => setInventoryName(event.target.value)} placeholder="Item name" /></label>
              <div className="memory-two-col">
                <label><span>Quantity</span><input type="number" min={1} max={9999} value={inventoryQuantity} onChange={(event) => setInventoryQuantity(Number(event.target.value))} /></label>
                <label><span>Status</span><select value={inventoryState} onChange={(event) => setInventoryState(event.target.value as ProcurementState)}>{PROCUREMENT_STATES.map((state) => <option key={state} value={state}>{procurementLabel(state)}</option>)}</select></label>
              </div>
              <label><span>Reference</span><input value={inventoryReference} maxLength={160} onChange={(event) => setInventoryReference(event.target.value)} placeholder="Reference (optional)" /></label>
              <button disabled={busy || !canEdit || !inventoryName.trim()}>Add item</button>
            </form>
          </section>
        </div>
      )}
    </main>
  )
}
