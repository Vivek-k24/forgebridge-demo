import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { apiRequest, CSRF_HEADERS, formatApiFailure } from './api'
import { newIdempotencyKey, partGraphDeviceId } from './device'
import './repair-memory.css'

type MemoryView = 'fasteners' | 'evidence' | 'inventory'
type LeaseStatus = 'available' | 'owned' | 'held_by_other'
type FastenerState = 'installed' | 'removed' | 'stored' | 'missing' | 'damaged' | 'replaced'
type ProcurementState = 'needed' | 'ordered' | 'available' | 'unavailable'
type ObservationCategory =
  | 'general'
  | 'condition'
  | 'damage'
  | 'part_number'
  | 'before'
  | 'after'
  | 'removed_part'
  | 'current_step'
type PhotoPurpose =
  | 'current_step'
  | 'removed_part'
  | 'fastener'
  | 'damage'
  | 'part_number'
  | 'before'
  | 'after'
  | 'general'

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

type StorageLocation = {
  id: string
  session_id: string
  label: string
  notes: string | null
  created_at: string
}

type Fastener = {
  id: string
  session_id: string
  kind: 'fastener' | 'small_part'
  label: string
  origin: string | null
  position: string | null
  physical_state: FastenerState
  storage_location_id: string | null
  notes: string | null
  created_at: string
  updated_at: string
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

type Observation = {
  id: string
  session_id: string
  category: ObservationCategory
  text: string
  source: 'user' | 'ai_proposed'
  review_state: 'confirmed' | 'proposed' | 'rejected'
  fastener_id: string | null
  created_at: string
}

type PhotoEvidence = {
  id: string
  session_id: string
  purpose: PhotoPurpose
  observation_id: string | null
  fastener_id: string | null
  original_filename: string | null
  media_type: string
  byte_size: number
  content_url: string
  created_at: string
}

type FastenerDraft = { state: FastenerState; storageLocationId: string }

const VIEWS: { key: MemoryView; label: string }[] = [
  { key: 'fasteners', label: 'Fasteners' },
  { key: 'evidence', label: 'Evidence' },
  { key: 'inventory', label: 'Inventory' },
]

function headers(deviceId: string, prefix: string): Record<string, string> {
  return {
    ...CSRF_HEADERS,
    'X-PartGraph-Device-ID': deviceId,
    'Idempotency-Key': newIdempotencyKey(prefix),
  }
}

function jsonHeaders(deviceId: string, prefix: string): Record<string, string> {
  return { ...headers(deviceId, prefix), 'Content-Type': 'application/json' }
}

function vehicleLabel(snapshot: ResumeSnapshot | null): string {
  if (!snapshot) return ''
  const identity = snapshot.vehicle.identity
  const base = [identity.year, identity.make, identity.model, identity.trim].filter(Boolean).join(' ')
  return snapshot.vehicle.nickname ? `${snapshot.vehicle.nickname} · ${base}` : base
}

export function RepairMemoryWorkspace({ initialView }: { initialView: MemoryView }) {
  const deviceId = useMemo(() => partGraphDeviceId(), [])
  const [view, setView] = useState<MemoryView>(initialView)
  const [sessions, setSessions] = useState<RepairSession[]>([])
  const [sessionId, setSessionId] = useState('')
  const [snapshot, setSnapshot] = useState<ResumeSnapshot | null>(null)
  const [locations, setLocations] = useState<StorageLocation[]>([])
  const [fasteners, setFasteners] = useState<Fastener[]>([])
  const [inventory, setInventory] = useState<InventoryItem[]>([])
  const [observations, setObservations] = useState<Observation[]>([])
  const [photos, setPhotos] = useState<PhotoEvidence[]>([])
  const [fastenerDrafts, setFastenerDrafts] = useState<Record<string, FastenerDraft>>({})
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [locationLabel, setLocationLabel] = useState('')
  const [fastenerLabel, setFastenerLabel] = useState('')
  const [fastenerOrigin, setFastenerOrigin] = useState('')
  const [fastenerPosition, setFastenerPosition] = useState('')
  const [fastenerState, setFastenerState] = useState<FastenerState>('removed')
  const [fastenerLocation, setFastenerLocation] = useState('')

  const [inventoryName, setInventoryName] = useState('')
  const [inventoryQuantity, setInventoryQuantity] = useState(1)
  const [inventoryState, setInventoryState] = useState<ProcurementState>('needed')
  const [inventoryReference, setInventoryReference] = useState('')

  const [observationCategory, setObservationCategory] = useState<ObservationCategory>('general')
  const [observationText, setObservationText] = useState('')
  const [observationFastener, setObservationFastener] = useState('')
  const [photoPurpose, setPhotoPurpose] = useState<PhotoPurpose>('general')
  const [photoFastener, setPhotoFastener] = useState('')
  const [photoFile, setPhotoFile] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string | null>(null)

  useEffect(() => setView(initialView), [initialView])

  useEffect(() => {
    if (!photoFile) {
      setPhotoPreview(null)
      return
    }
    const url = URL.createObjectURL(photoFile)
    setPhotoPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [photoFile])

  const loadMemory = useCallback(
    async (selectedSessionId: string) => {
      const [resume, locationRows, fastenerRows, inventoryRows, observationRows, photoRows] =
        await Promise.all([
          apiRequest<ResumeSnapshot>(
            `/api/v1/repair-sessions/${selectedSessionId}/resume`,
            { headers: { 'X-PartGraph-Device-ID': deviceId } },
            { retryIdempotent: true },
          ),
          apiRequest<StorageLocation[]>(`/api/v1/repair-sessions/${selectedSessionId}/storage-locations`),
          apiRequest<Fastener[]>(`/api/v1/repair-sessions/${selectedSessionId}/fasteners`),
          apiRequest<InventoryItem[]>(`/api/v1/repair-sessions/${selectedSessionId}/inventory`),
          apiRequest<Observation[]>(`/api/v1/repair-sessions/${selectedSessionId}/observations`),
          apiRequest<PhotoEvidence[]>(`/api/v1/repair-sessions/${selectedSessionId}/photos`),
        ])
      setSnapshot(resume)
      setLocations(locationRows)
      setFasteners(fastenerRows)
      setInventory(inventoryRows)
      setObservations(observationRows)
      setPhotos(photoRows)
      setFastenerDrafts(
        Object.fromEntries(
          fastenerRows.map((item) => [
            item.id,
            { state: item.physical_state, storageLocationId: item.storage_location_id ?? '' },
          ]),
        ),
      )
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
        if (first) await loadMemory(first)
      } catch (failure) {
        if (active) setError(formatApiFailure(failure, 'Could not load repair memory.'))
      } finally {
        if (active) setLoading(false)
      }
    }
    void initialize()
    return () => {
      active = false
    }
  }, [loadMemory])

  async function selectSession(nextSessionId: string) {
    setSessionId(nextSessionId)
    setError(null)
    setMessage(null)
    if (nextSessionId) await loadMemory(nextSessionId)
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
      await loadMemory(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not acquire editing control.'))
    } finally {
      setBusy(false)
    }
  }

  async function createLocation(event: FormEvent) {
    event.preventDefault()
    if (!sessionId || !locationLabel.trim()) return
    try {
      setBusy(true)
      setError(null)
      await apiRequest(`/api/v1/repair-sessions/${sessionId}/storage-locations`, {
        method: 'POST',
        headers: jsonHeaders(deviceId, 'memory_location'),
        body: JSON.stringify({ label: locationLabel.trim() }),
      })
      setLocationLabel('')
      setMessage('Storage location recorded.')
      await loadMemory(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not save the storage location.'))
    } finally {
      setBusy(false)
    }
  }

  async function createFastener(event: FormEvent) {
    event.preventDefault()
    if (!sessionId || !fastenerLabel.trim()) return
    if (fastenerState === 'stored' && !fastenerLocation) {
      setError('Choose a storage location before marking a fastener stored.')
      return
    }
    try {
      setBusy(true)
      setError(null)
      await apiRequest(`/api/v1/repair-sessions/${sessionId}/fasteners`, {
        method: 'POST',
        headers: jsonHeaders(deviceId, 'memory_fastener'),
        body: JSON.stringify({
          label: fastenerLabel.trim(),
          origin: fastenerOrigin.trim() || null,
          position: fastenerPosition.trim() || null,
          physical_state: fastenerState,
          storage_location_id: fastenerState === 'stored' ? fastenerLocation : null,
        }),
      })
      setFastenerLabel('')
      setFastenerOrigin('')
      setFastenerPosition('')
      setFastenerState('removed')
      setFastenerLocation('')
      setMessage('Fastener state recorded.')
      await loadMemory(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not record the fastener.'))
    } finally {
      setBusy(false)
    }
  }

  async function saveFastenerState(item: Fastener) {
    const draft = fastenerDrafts[item.id]
    if (!draft || !sessionId) return
    if (draft.state === 'stored' && !draft.storageLocationId) {
      setError('Stored fasteners require a storage location.')
      return
    }
    try {
      setBusy(true)
      setError(null)
      await apiRequest(`/api/v1/repair-sessions/${sessionId}/fasteners/${item.id}`, {
        method: 'PATCH',
        headers: jsonHeaders(deviceId, 'memory_fastener_state'),
        body: JSON.stringify({
          physical_state: draft.state,
          storage_location_id: draft.state === 'stored' ? draft.storageLocationId : null,
          notes: item.notes,
        }),
      })
      setMessage(`${item.label} updated.`)
      await loadMemory(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not update the fastener.'))
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
        headers: jsonHeaders(deviceId, 'memory_inventory'),
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
      setMessage('Inventory requirement recorded.')
      await loadMemory(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not record inventory.'))
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
        headers: jsonHeaders(deviceId, 'memory_inventory_state'),
        body: JSON.stringify({ procurement_state: state, quantity: item.quantity, notes: item.notes }),
      })
      setMessage(`${item.name} marked ${state}.`)
      await loadMemory(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not update inventory.'))
    } finally {
      setBusy(false)
    }
  }

  async function createObservation(event: FormEvent) {
    event.preventDefault()
    if (!sessionId || !observationText.trim()) return
    try {
      setBusy(true)
      setError(null)
      await apiRequest(`/api/v1/repair-sessions/${sessionId}/observations`, {
        method: 'POST',
        headers: jsonHeaders(deviceId, 'memory_observation'),
        body: JSON.stringify({
          category: observationCategory,
          text: observationText.trim(),
          fastener_id: observationFastener || null,
        }),
      })
      setObservationText('')
      setObservationFastener('')
      setMessage('Observation saved as user-confirmed evidence.')
      await loadMemory(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not save the observation.'))
    } finally {
      setBusy(false)
    }
  }

  async function uploadPhoto(event: FormEvent) {
    event.preventDefault()
    if (!sessionId || !photoFile) return
    if (photoPurpose === 'fastener' && !photoFastener) {
      setError('Choose the fastener this photo belongs to.')
      return
    }
    const body = new FormData()
    body.append('photo', photoFile)
    body.append('purpose', photoPurpose)
    if (photoFastener) body.append('fastener_id', photoFastener)
    try {
      setBusy(true)
      setError(null)
      await apiRequest(`/api/v1/repair-sessions/${sessionId}/photos`, {
        method: 'POST',
        headers: headers(deviceId, 'memory_photo'),
        body,
      })
      setPhotoFile(null)
      setPhotoFastener('')
      setPhotoPurpose('general')
      setMessage('Photo evidence attached to this repair session.')
      await loadMemory(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not upload photo evidence.'))
    } finally {
      setBusy(false)
    }
  }

  async function deletePhoto(photo: PhotoEvidence) {
    if (!sessionId || !window.confirm('Delete this photo evidence?')) return
    try {
      setBusy(true)
      setError(null)
      await apiRequest(`/api/v1/repair-sessions/${sessionId}/photos/${photo.id}`, {
        method: 'DELETE',
        headers: headers(deviceId, 'memory_photo_delete'),
      })
      setMessage('Photo evidence deleted.')
      await loadMemory(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not delete photo evidence.'))
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <p className="memory-loading">Loading repair memory…</p>

  const canEdit = snapshot?.lease.can_edit ?? false

  return (
    <main className="memory-shell">
      <header className="memory-heading">
        <div>
          <p className="eyebrow">PARTGRAPH · PHYSICAL MEMORY</p>
          <h1>Keep the repair organized while the car is apart.</h1>
          <p className="lede">
            Track what came off, where it went, what you still need, and the evidence you captured.
            These are recorded facts—not generated repair instructions.
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
              <option key={item.id} value={item.id}>{item.title} · event {item.current_sequence}</option>
            ))}
          </select>
        </label>
        {snapshot && (
          <div className="memory-session-state">
            <strong>{vehicleLabel(snapshot)}</strong>
            <span>{snapshot.session.status} · {snapshot.lease.status.replaceAll('_', ' ')}</span>
          </div>
        )}
        {snapshot && !canEdit && snapshot.session.status !== 'archived' && (
          <button
            type="button"
            disabled={busy}
            onClick={() => void acquireLease(snapshot.lease.status === 'held_by_other')}
          >
            {snapshot.lease.status === 'held_by_other' ? 'Take over session' : 'Take editing control'}
          </button>
        )}
      </section>

      {!snapshot ? (
        <section className="memory-empty panel">
          <h2>No active repair selected.</h2>
          <p>Start or resume a Repair Session before recording physical repair memory.</p>
        </section>
      ) : (
        <>
          <nav className="memory-tabs" aria-label="Repair memory views">
            {VIEWS.map((item) => (
              <button
                key={item.key}
                type="button"
                className={view === item.key ? 'memory-tab memory-tab--active' : 'memory-tab'}
                onClick={() => setView(item.key)}
              >
                {item.label}
              </button>
            ))}
          </nav>

          {view === 'fasteners' && (
            <div className="memory-grid">
              <section className="panel memory-form-panel">
                <p className="eyebrow">STORAGE</p>
                <h2>Where did the hardware go?</h2>
                <form onSubmit={createLocation}>
                  <label>
                    <span>Storage location</span>
                    <input
                      value={locationLabel}
                      maxLength={120}
                      placeholder="Magnetic tray A, bag 3, shelf bin…"
                      onChange={(event) => setLocationLabel(event.target.value)}
                    />
                  </label>
                  <button disabled={busy || !canEdit || !locationLabel.trim()}>Save location</button>
                </form>
                <div className="memory-chip-list">
                  {locations.map((item) => <span key={item.id}>{item.label}</span>)}
                </div>
              </section>

              <section className="panel memory-form-panel">
                <p className="eyebrow">FASTENER / SMALL PART</p>
                <h2>Record it before it disappears.</h2>
                <form onSubmit={createFastener}>
                  <label><span>Label</span><input value={fastenerLabel} maxLength={120} onChange={(event) => setFastenerLabel(event.target.value)} placeholder="Upper support bolt" /></label>
                  <div className="memory-two-col">
                    <label><span>Origin</span><input value={fastenerOrigin} maxLength={160} onChange={(event) => setFastenerOrigin(event.target.value)} placeholder="Radiator support" /></label>
                    <label><span>Position</span><input value={fastenerPosition} maxLength={160} onChange={(event) => setFastenerPosition(event.target.value)} placeholder="Driver side" /></label>
                  </div>
                  <div className="memory-two-col">
                    <label><span>Physical state</span><select value={fastenerState} onChange={(event) => setFastenerState(event.target.value as FastenerState)}>{(['installed', 'removed', 'stored', 'missing', 'damaged', 'replaced'] as FastenerState[]).map((state) => <option key={state}>{state}</option>)}</select></label>
                    <label><span>Stored in</span><select value={fastenerLocation} disabled={fastenerState !== 'stored'} onChange={(event) => setFastenerLocation(event.target.value)}><option value="">Choose location</option>{locations.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
                  </div>
                  <button disabled={busy || !canEdit || !fastenerLabel.trim()}>Record fastener</button>
                </form>
              </section>

              <section className="panel memory-list-panel memory-span-all">
                <div className="memory-section-title"><div><p className="eyebrow">CURRENT PHYSICAL STATE</p><h2>Fasteners & small parts</h2></div><span>{fasteners.length}</span></div>
                {fasteners.length === 0 ? <p className="memory-muted">Nothing recorded yet.</p> : (
                  <div className="memory-card-grid">
                    {fasteners.map((item) => {
                      const draft = fastenerDrafts[item.id] ?? { state: item.physical_state, storageLocationId: item.storage_location_id ?? '' }
                      return (
                        <article className="memory-card" key={item.id}>
                          <div><strong>{item.label}</strong><span>{[item.origin, item.position].filter(Boolean).join(' · ') || 'Origin not recorded'}</span></div>
                          <div className="memory-two-col">
                            <select value={draft.state} disabled={!canEdit || busy} onChange={(event) => setFastenerDrafts((current) => ({ ...current, [item.id]: { ...draft, state: event.target.value as FastenerState } }))}>{(['installed', 'removed', 'stored', 'missing', 'damaged', 'replaced'] as FastenerState[]).map((state) => <option key={state}>{state}</option>)}</select>
                            <select value={draft.storageLocationId} disabled={!canEdit || busy || draft.state !== 'stored'} onChange={(event) => setFastenerDrafts((current) => ({ ...current, [item.id]: { ...draft, storageLocationId: event.target.value } }))}><option value="">No location</option>{locations.map((location) => <option key={location.id} value={location.id}>{location.label}</option>)}</select>
                          </div>
                          <button className="secondary" disabled={!canEdit || busy} onClick={() => void saveFastenerState(item)}>Save state</button>
                        </article>
                      )
                    })}
                  </div>
                )}
              </section>
            </div>
          )}

          {view === 'inventory' && (
            <div className="memory-grid">
              <section className="panel memory-form-panel">
                <p className="eyebrow">PARTS READINESS</p>
                <h2>Record what this repair needs.</h2>
                <form onSubmit={createInventory}>
                  <label><span>Item</span><input value={inventoryName} maxLength={160} onChange={(event) => setInventoryName(event.target.value)} placeholder="Replacement support bolt" /></label>
                  <div className="memory-two-col"><label><span>Quantity</span><input type="number" min={1} max={9999} value={inventoryQuantity} onChange={(event) => setInventoryQuantity(Number(event.target.value))} /></label><label><span>Procurement</span><select value={inventoryState} onChange={(event) => setInventoryState(event.target.value as ProcurementState)}>{(['needed', 'ordered', 'available', 'unavailable'] as ProcurementState[]).map((state) => <option key={state}>{state}</option>)}</select></label></div>
                  <label><span>Reference</span><input value={inventoryReference} maxLength={160} onChange={(event) => setInventoryReference(event.target.value)} placeholder="Receipt, store, candidate part number…" /></label>
                  <button disabled={busy || !canEdit || !inventoryName.trim()}>Record inventory</button>
                </form>
              </section>
              <section className="panel memory-list-panel">
                <div className="memory-section-title"><div><p className="eyebrow">PROCUREMENT STATE</p><h2>Inventory</h2></div><span>{inventory.length}</span></div>
                <div className="memory-card-grid">
                  {inventory.map((item) => (
                    <article className="memory-card" key={item.id}>
                      <div><strong>{item.name}</strong><span>qty {item.quantity}{item.reference ? ` · ${item.reference}` : ''}</span></div>
                      <select value={item.procurement_state} disabled={!canEdit || busy} onChange={(event) => void changeInventoryState(item, event.target.value as ProcurementState)}>{(['needed', 'ordered', 'available', 'unavailable'] as ProcurementState[]).map((state) => <option key={state}>{state}</option>)}</select>
                    </article>
                  ))}
                  {inventory.length === 0 && <p className="memory-muted">No inventory requirements recorded.</p>}
                </div>
              </section>
            </div>
          )}

          {view === 'evidence' && (
            <div className="memory-grid">
              <section className="panel memory-form-panel">
                <p className="eyebrow">OBSERVATION</p>
                <h2>Record what you actually see.</h2>
                <form onSubmit={createObservation}>
                  <div className="memory-two-col"><label><span>Category</span><select value={observationCategory} onChange={(event) => setObservationCategory(event.target.value as ObservationCategory)}>{(['general', 'condition', 'damage', 'part_number', 'before', 'after', 'removed_part', 'current_step'] as ObservationCategory[]).map((category) => <option key={category} value={category}>{category.replaceAll('_', ' ')}</option>)}</select></label><label><span>Fastener (optional)</span><select value={observationFastener} onChange={(event) => setObservationFastener(event.target.value)}><option value="">Not attached</option>{fasteners.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label></div>
                  <label><span>Observation</span><textarea value={observationText} maxLength={1000} rows={4} onChange={(event) => setObservationText(event.target.value)} placeholder="What changed, what is damaged, what marking did you find?" /></label>
                  <button disabled={busy || !canEdit || !observationText.trim()}>Save observation</button>
                </form>
              </section>

              <section className="panel memory-form-panel">
                <p className="eyebrow">PHOTO EVIDENCE</p>
                <h2>Capture before you move on.</h2>
                <form onSubmit={uploadPhoto}>
                  <div className="memory-two-col"><label><span>Purpose</span><select value={photoPurpose} onChange={(event) => setPhotoPurpose(event.target.value as PhotoPurpose)}>{(['general', 'current_step', 'removed_part', 'fastener', 'damage', 'part_number', 'before', 'after'] as PhotoPurpose[]).map((purpose) => <option key={purpose} value={purpose}>{purpose.replaceAll('_', ' ')}</option>)}</select></label><label><span>Fastener</span><select value={photoFastener} disabled={photoPurpose !== 'fastener'} onChange={(event) => setPhotoFastener(event.target.value)}><option value="">Choose fastener</option>{fasteners.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label></div>
                  <label className="memory-photo-input"><span>Camera / photo</span><input type="file" accept="image/jpeg,image/png,image/webp,image/heic,.heic" capture="environment" onChange={(event) => setPhotoFile(event.target.files?.[0] ?? null)} /></label>
                  {photoPreview && <img className="memory-preview" src={photoPreview} alt="Pending upload preview" />}
                  <button disabled={busy || !canEdit || !photoFile}>Attach photo</button>
                </form>
              </section>

              <section className="panel memory-list-panel memory-span-all">
                <div className="memory-section-title"><div><p className="eyebrow">RECORDED EVIDENCE</p><h2>Observations & photos</h2></div><span>{observations.length + photos.length}</span></div>
                <div className="memory-evidence-grid">
                  <div>
                    <h3>Observations</h3>
                    {observations.map((item) => <article className="memory-card" key={item.id}><strong>{item.category.replaceAll('_', ' ')}</strong><p>{item.text}</p><small>{item.source} · {item.review_state}</small></article>)}
                    {observations.length === 0 && <p className="memory-muted">No observations recorded.</p>}
                  </div>
                  <div>
                    <h3>Photos</h3>
                    <div className="memory-photo-grid">
                      {photos.map((photo) => <article className="memory-photo-card" key={photo.id}><img src={photo.content_url} alt={`${photo.purpose.replaceAll('_', ' ')} evidence`} loading="lazy" /><div><strong>{photo.purpose.replaceAll('_', ' ')}</strong><small>{Math.ceil(photo.byte_size / 1024)} KB</small></div><button className="secondary" disabled={!canEdit || busy} onClick={() => void deletePhoto(photo)}>Delete</button></article>)}
                    </div>
                    {photos.length === 0 && <p className="memory-muted">No photo evidence attached.</p>}
                  </div>
                </div>
              </section>
            </div>
          )}
        </>
      )}
    </main>
  )
}
