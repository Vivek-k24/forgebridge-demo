import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { apiRequest, CSRF_HEADERS, formatApiFailure } from './api'
import { newIdempotencyKey, partGraphDeviceId } from './device'
import './repair-memory.css'

type LeaseStatus = 'available' | 'owned' | 'held_by_other'
type ProcurementState = 'needed' | 'ordered' | 'available' | 'unavailable'

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

const PROCUREMENT_STATES: ProcurementState[] = [
  'needed',
  'ordered',
  'available',
  'unavailable',
]

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
  const base = [identity.year, identity.make, identity.model, identity.trim]
    .filter(Boolean)
    .join(' ')
  return snapshot.vehicle.nickname ? `${snapshot.vehicle.nickname} · ${base}` : base
}

function procurementLabel(state: ProcurementState): string {
  switch (state) {
    case 'available':
      return 'Have it'
    case 'ordered':
      return 'Ordered'
    case 'unavailable':
      return 'Cannot get yet'
    default:
      return 'Need it'
  }
}

export function RepairMemoryWorkspace() {
  const deviceId = useMemo(() => partGraphDeviceId(), [])
  const [sessions, setSessions] = useState<RepairSession[]>([])
  const [sessionId, setSessionId] = useState('')
  const [snapshot, setSnapshot] = useState<ResumeSnapshot | null>(null)
  const [inventory, setInventory] = useState<InventoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [inventoryName, setInventoryName] = useState('')
  const [inventoryQuantity, setInventoryQuantity] = useState(1)
  const [inventoryState, setInventoryState] = useState<ProcurementState>('needed')
  const [inventoryReference, setInventoryReference] = useState('')

  const loadReadiness = useCallback(
    async (selectedSessionId: string) => {
      const [resume, inventoryRows] = await Promise.all([
        apiRequest<ResumeSnapshot>(
          `/api/v1/repair-sessions/${selectedSessionId}/resume`,
          { headers: { 'X-PartGraph-Device-ID': deviceId } },
          { retryIdempotent: true },
        ),
        apiRequest<InventoryItem[]>(
          `/api/v1/repair-sessions/${selectedSessionId}/inventory`,
        ),
      ])
      setSnapshot(resume)
      setInventory(inventoryRows)
    },
    [deviceId],
  )

  useEffect(() => {
    let active = true

    async function initialize() {
      try {
        setLoading(true)
        const rows = await apiRequest<RepairSession[]>('/api/v1/repair-sessions')
        if (!active) return
        setSessions(rows)
        const first = rows[0]?.id ?? ''
        setSessionId(first)
        if (first) await loadReadiness(first)
      } catch (failure) {
        if (active) setError(formatApiFailure(failure, 'Could not load repair readiness.'))
      } finally {
        if (active) setLoading(false)
      }
    }

    void initialize()
    return () => {
      active = false
    }
  }, [loadReadiness])

  async function selectSession(nextSessionId: string) {
    setSessionId(nextSessionId)
    setSnapshot(null)
    setInventory([])
    setError(null)
    setMessage(null)
    if (nextSessionId) await loadReadiness(nextSessionId)
  }

  async function acquireLease(takeover: boolean) {
    if (!sessionId) return
    try {
      setBusy(true)
      setError(null)
      await apiRequest(
        `/api/v1/repair-sessions/${sessionId}/lease/${takeover ? 'takeover' : 'acquire'}`,
        {
          method: 'POST',
          headers: { ...CSRF_HEADERS, 'X-PartGraph-Device-ID': deviceId },
        },
      )
      setMessage(
        takeover ? 'Editing control moved to this device.' : 'Editing control acquired.',
      )
      await loadReadiness(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not acquire editing control.'))
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
        body: JSON.stringify({
          procurement_state: state,
          quantity: item.quantity,
          notes: item.notes,
        }),
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
  const availableCount = inventory.filter(
    (item) => item.procurement_state === 'available',
  ).length
  const orderedCount = inventory.filter(
    (item) => item.procurement_state === 'ordered',
  ).length
  const missingCount = inventory.filter(
    (item) => item.procurement_state === 'needed' || item.procurement_state === 'unavailable',
  ).length

  return (
    <main className="memory-shell">
      <header className="memory-heading">
        <div>
          <p className="eyebrow">PARTGRAPH · REPAIR READINESS</p>
          <h1>Know what you need before the repair gets complicated.</h1>
          <p className="lede">
            Inventory is the readiness checklist for the repair: tools, parts, fluids,
            consumables, hardware, and other physical requirements. PartGraph will supply
            verified requirements from the repair definition; you tell it what you already
            have and what is still missing.
          </p>
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
            {sessions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title} · event {item.current_sequence}
              </option>
            ))}
          </select>
        </label>
        {snapshot && (
          <div className="memory-session-state">
            <strong>{vehicleLabel(snapshot)}</strong>
            <span>
              {snapshot.session.status} · {snapshot.lease.status.replaceAll('_', ' ')}
            </span>
          </div>
        )}
        {snapshot && !canEdit && snapshot.session.status !== 'archived' && (
          <button
            type="button"
            disabled={busy}
            onClick={() => void acquireLease(snapshot.lease.status === 'held_by_other')}
          >
            {snapshot.lease.status === 'held_by_other'
              ? 'Take over session'
              : 'Take editing control'}
          </button>
        )}
      </section>

      {!snapshot ? (
        <section className="memory-empty panel">
          <h2>No active repair selected.</h2>
          <p>Start or resume a Repair Session before checking repair readiness.</p>
        </section>
      ) : (
        <div className="memory-grid">
          <section className="panel memory-list-panel memory-span-all">
            <div className="memory-section-title">
              <div>
                <p className="eyebrow">READINESS AT A GLANCE</p>
                <h2>What is ready and what is missing?</h2>
              </div>
              <span>{inventory.length}</span>
            </div>
            <div className="memory-chip-list">
              <span>{availableCount} have</span>
              <span>{orderedCount} ordered</span>
              <span>{missingCount} missing</span>
            </div>
            {inventory.length === 0 && (
              <p className="memory-muted">
                No requirements are loaded yet. Verified repair definitions will populate this
                list automatically in the next domain block.
              </p>
            )}
          </section>

          <section className="panel memory-list-panel">
            <div className="memory-section-title">
              <div>
                <p className="eyebrow">REPAIR INVENTORY</p>
                <h2>Requirements</h2>
              </div>
              <span>{inventory.length}</span>
            </div>
            <div className="memory-card-grid">
              {inventory.map((item) => (
                <article className="memory-card" key={item.id}>
                  <div>
                    <strong>{item.name}</strong>
                    <span>
                      qty {item.quantity}
                      {item.reference ? ` · ${item.reference}` : ''}
                    </span>
                  </div>
                  <label>
                    <span>Status</span>
                    <select
                      value={item.procurement_state}
                      disabled={!canEdit || busy}
                      onChange={(event) =>
                        void changeInventoryState(
                          item,
                          event.target.value as ProcurementState,
                        )
                      }
                    >
                      {PROCUREMENT_STATES.map((state) => (
                        <option key={state} value={state}>
                          {procurementLabel(state)}
                        </option>
                      ))}
                    </select>
                  </label>
                </article>
              ))}
            </div>
          </section>

          <section className="panel memory-form-panel">
            <p className="eyebrow">MANUAL FALLBACK</p>
            <h2>Add something the repair definition does not know yet.</h2>
            <p className="memory-muted">
              This is a fallback, not the intended primary workflow. Future verified repair
              definitions will provide the required list automatically.
            </p>
            <form onSubmit={createInventory}>
              <label>
                <span>Item</span>
                <input
                  value={inventoryName}
                  maxLength={160}
                  onChange={(event) => setInventoryName(event.target.value)}
                  placeholder="Tool, part, fluid, clip, bolt…"
                />
              </label>
              <div className="memory-two-col">
                <label>
                  <span>Quantity</span>
                  <input
                    type="number"
                    min={1}
                    max={9999}
                    value={inventoryQuantity}
                    onChange={(event) => setInventoryQuantity(Number(event.target.value))}
                  />
                </label>
                <label>
                  <span>Status</span>
                  <select
                    value={inventoryState}
                    onChange={(event) =>
                      setInventoryState(event.target.value as ProcurementState)
                    }
                  >
                    {PROCUREMENT_STATES.map((state) => (
                      <option key={state} value={state}>
                        {procurementLabel(state)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label>
                <span>Reference</span>
                <input
                  value={inventoryReference}
                  maxLength={160}
                  onChange={(event) => setInventoryReference(event.target.value)}
                  placeholder="Store, receipt, known part reference…"
                />
              </label>
              <button disabled={busy || !canEdit || !inventoryName.trim()}>
                Add temporary requirement
              </button>
            </form>
          </section>
        </div>
      )}
    </main>
  )
}
