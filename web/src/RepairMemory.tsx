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
    case 'garage': return 'From Garage inventory'
    case 'existing_vehicle': return 'Reuse existing vehicle item'
    case 'session': return 'Confirmed for this repair'
    default: return 'Not confirmed yet'
  }
}

function requirementQuantity(item: RepairReadinessItem): string {
  if (item.required_quantity === null) return 'Quantity not established'
  return `Need ${item.required_quantity}${item.unit ? ` ${item.unit}` : ''}`
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
      setMessage(takeover ? 'Editing control moved to this device.' : 'Editing control acquired.')
      await loadReadiness(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not acquire editing control.'))
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
      setMessage('Verified repair requirements connected to this existing session.')
      await loadReadiness(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not load the verified repair definition.'))
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
      setError(formatApiFailure(failure, 'Could not update verified repair readiness.'))
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
      setMessage('Temporary repair requirement recorded.')
      await loadReadiness(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not record the inventory item.'))
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
      setError(formatApiFailure(failure, 'Could not update repair readiness.'))
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

  return (
    <main className="memory-shell">
      <header className="memory-heading">
        <div>
          <p className="eyebrow">PARTGRAPH · REPAIR READINESS</p>
          <h1>Know what you need before the repair gets complicated.</h1>
          <p className="lede">Readiness covers tools, parts, fluids, consumables, hardware, and setup requirements. PartGraph supplies verified requirements for the exact vehicle configuration; you mainly confirm what you have and what is still missing.</p>
        </div>
        <span className="memory-device">device {deviceId.slice(0, 8)}</span>
      </header>

      {error && <div className="memory-alert memory-alert--error">{error}</div>}
      {message && <div className="memory-alert memory-alert--success">{message}</div>}

      <section className="memory-session-bar panel">
        <label>
          <span>Repair session</span>
          <select value={sessionId} onChange={(event) => void selectSession(event.target.value)}>
            {sessions.length === 0 && <option value="">No active repair sessions</option>}
            {sessions.map((item) => <option key={item.id} value={item.id}>{item.title} · event {item.current_sequence}</option>)}
          </select>
        </label>
        {snapshot && <div className="memory-session-state"><strong>{vehicleLabel(snapshot)}</strong><span>{snapshot.session.status} · {snapshot.lease.status.replaceAll('_', ' ')}</span></div>}
        {snapshot && !canEdit && snapshot.session.status !== 'archived' && (
          <button type="button" disabled={busy} onClick={() => void acquireLease(snapshot.lease.status === 'held_by_other')}>
            {snapshot.lease.status === 'held_by_other' ? 'Take over session' : 'Take editing control'}
          </button>
        )}
      </section>

      {!snapshot ? (
        <section className="memory-empty panel"><h2>No active repair selected.</h2><p>Start or resume a Repair Session before checking repair readiness.</p></section>
      ) : (
        <div className="memory-grid">
          {!verifiedBound && (
            <section className="panel memory-list-panel memory-span-all">
              <div className="memory-section-title"><div><p className="eyebrow">EXISTING UNBOUND SESSION</p><h2>Connect verified requirements if this repair was started without them.</h2></div></div>
              <p className="memory-muted">New sessions now offer verified repair binding during Start Repair. This recovery control remains for older or intentionally unbound sessions.</p>
              {repairOptions?.vehicle_resolution === 'unresolved' ? (
                <p className="memory-muted">This saved vehicle is not resolved to an exact canonical configuration yet. Verified repair requirements stay disabled rather than guessing fitment.</p>
              ) : repairOptions && repairOptions.options.length > 0 ? (
                <div className="memory-two-col">
                  <label><span>Verified repair</span><select value={selectedRepairKey} disabled={busy} onChange={(event) => setSelectedRepairKey(event.target.value)}>{repairOptions.options.map((option) => <option key={option.repair_definition_id} value={option.repair_key}>{option.title} · v{option.version}</option>)}</select></label>
                  <button type="button" disabled={busy || !canEdit || !selectedRepairKey} onClick={() => void bindVerifiedRepair()}>Connect verified requirements</button>
                </div>
              ) : <p className="memory-muted">No verified repair definition is available for this exact vehicle configuration yet. Temporary/manual inventory remains available below.</p>}
            </section>
          )}

          {verifiedBound && readiness && (
            <>
              <section className="panel memory-list-panel memory-span-all">
                <div className="memory-section-title">
                  <div><p className="eyebrow">VERIFIED READINESS</p><h2>{readiness.repair?.title}</h2><p className="memory-muted">Exact repair definition v{readiness.repair?.version}{readiness.repair?.definition_status === 'superseded' ? ' · this session remains pinned to its original verified version' : ''}</p></div>
                  <span>{readiness.summary.total}</span>
                </div>
                <div className="memory-chip-list"><span>{readiness.summary.ready} have</span><span>{readiness.summary.missing} missing</span><span>{readiness.summary.ordered} ordered</span><span>{readiness.summary.unavailable} unavailable</span><span>{readiness.summary.blocked} blocking</span></div>
              </section>

              <section className="panel memory-list-panel memory-span-all">
                <div className="memory-section-title"><div><p className="eyebrow">WHAT THIS REPAIR REQUIRES</p><h2>Verified requirements</h2></div><span>{readiness.requirements.length}</span></div>
                <div className="memory-card-grid">
                  {readiness.requirements.map((item) => (
                    <article className="memory-card" key={item.requirement_definition_id}>
                      <div><strong>{item.display_name}</strong><span>{item.category.replaceAll('_', ' ')} · {requirementQuantity(item)}</span><span>{readinessSourceLabel(item.readiness_source)}</span>{item.operation_keys.length > 0 && <span>Used in: {item.operation_keys.join(', ')}</span>}</div>
                      <label><span>Status</span><select value={item.readiness_state} disabled={!canEdit || busy} onChange={(event) => void changeVerifiedReadiness(item, event.target.value as ReadinessState)}>{READINESS_STATES.map((state) => <option key={state} value={state}>{readinessLabel(state)}</option>)}</select></label>
                    </article>
                  ))}
                </div>
              </section>
            </>
          )}

          <section className="panel memory-list-panel">
            <div className="memory-section-title"><div><p className="eyebrow">MANUAL / EXCEPTION MEMORY</p><h2>Temporary requirements</h2></div><span>{inventory.length}</span></div>
            <p className="memory-muted">Use this only for something the verified definition does not cover yet, or while no verified definition exists for the repair.</p>
            <div className="memory-chip-list"><span>{manualAvailableCount} have</span><span>{manualOrderedCount} ordered</span><span>{manualMissingCount} missing</span></div>
            <div className="memory-card-grid">
              {inventory.map((item) => (
                <article className="memory-card" key={item.id}>
                  <div><strong>{item.name}</strong><span>qty {item.quantity}{item.reference ? ` · ${item.reference}` : ''}</span></div>
                  <label><span>Status</span><select value={item.procurement_state} disabled={!canEdit || busy} onChange={(event) => void changeInventoryState(item, event.target.value as ProcurementState)}>{PROCUREMENT_STATES.map((state) => <option key={state} value={state}>{procurementLabel(state)}</option>)}</select></label>
                </article>
              ))}
              {inventory.length === 0 && <p className="memory-muted">No temporary requirements recorded.</p>}
            </div>
          </section>

          <section className="panel memory-form-panel">
            <p className="eyebrow">MANUAL FALLBACK</p>
            <h2>Add an exception PartGraph does not know yet.</h2>
            <p className="memory-muted">Verified requirements are the primary workflow. This form preserves the ability to record a newly discovered tool, part, fluid, clip, bolt, or procurement blocker without pretending it is canonical repair truth.</p>
            <form onSubmit={createInventory}>
              <label><span>Item</span><input value={inventoryName} maxLength={160} onChange={(event) => setInventoryName(event.target.value)} placeholder="Tool, part, fluid, clip, bolt…" /></label>
              <div className="memory-two-col">
                <label><span>Quantity</span><input type="number" min={1} max={9999} value={inventoryQuantity} onChange={(event) => setInventoryQuantity(Number(event.target.value))} /></label>
                <label><span>Status</span><select value={inventoryState} onChange={(event) => setInventoryState(event.target.value as ProcurementState)}>{PROCUREMENT_STATES.map((state) => <option key={state} value={state}>{procurementLabel(state)}</option>)}</select></label>
              </div>
              <label><span>Reference</span><input value={inventoryReference} maxLength={160} onChange={(event) => setInventoryReference(event.target.value)} placeholder="Store, receipt, known part reference…" /></label>
              <button disabled={busy || !canEdit || !inventoryName.trim()}>Add temporary requirement</button>
            </form>
          </section>
        </div>
      )}
    </main>
  )
}
