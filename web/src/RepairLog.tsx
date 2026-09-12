import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { activeRepairSessionId, preferredRepairSessionId, setActiveRepairSessionId } from './active-repair'
import { apiRequest, formatApiFailure } from './api'
import { recoverableRepairMutation, repairDeviceId, repairMutationHeaders } from './repair-client'
import './repair-workspaces.css'

type RepairSession = { id: string; title: string; status: 'active' | 'paused' | 'archived'; current_sequence: number }
type ResumeSnapshot = { lease: { status: 'available' | 'owned' | 'held_by_other'; can_edit: boolean } }
type StorageLocation = { id: string; label: string; notes: string | null; created_at: string }
type FastenerState = 'installed' | 'removed' | 'stored' | 'missing' | 'damaged' | 'replaced'
type Fastener = { id: string; kind: 'fastener' | 'small_part'; label: string; origin: string | null; position: string | null; physical_state: FastenerState; storage_location_id: string | null; notes: string | null; updated_at: string }
type Observation = { id: string; category: string; text: string; source: 'user' | 'ai_proposed'; review_state: string; fastener_id: string | null; created_at: string }
type Photo = { id: string; purpose: string; observation_id: string | null; fastener_id: string | null; original_filename: string | null; media_type: string; byte_size: number; content_url: string; created_at: string }
type EventItem = { id: string; sequence: number; event_type: string; actor_device_id: string; payload: Record<string, unknown>; created_at: string }
type EventPage = { items: EventItem[]; next_after_sequence: number | null }

const OBSERVATION_CATEGORIES = ['general', 'condition', 'damage', 'part_number', 'before', 'after', 'removed_part', 'current_step'] as const
const PHOTO_PURPOSES = ['current_step', 'removed_part', 'fastener', 'damage', 'part_number', 'before', 'after', 'general'] as const

function human(value: string): string {
  return value.replaceAll('_', ' ')
}

async function loadEventHistory(sessionId: string): Promise<EventItem[]> {
  const items: EventItem[] = []
  let afterSequence: number | null = null

  while (true) {
    const cursor: string = afterSequence === null ? '' : `&after_sequence=${afterSequence}`
    const page: EventPage = await apiRequest<EventPage>(
      `/api/v1/repair-sessions/${sessionId}/events?limit=100${cursor}`,
      undefined,
      { retryIdempotent: true },
    )
    items.push(...page.items)
    if (page.next_after_sequence === null) return items
    if (page.next_after_sequence === afterSequence) {
      throw new Error('Repair event pagination did not advance.')
    }
    afterSequence = page.next_after_sequence
  }
}

export function RepairLogWorkspace() {
  const [sessions, setSessions] = useState<RepairSession[]>([])
  const [selectedId, setSelectedId] = useState(() => activeRepairSessionId() || '')
  const [resume, setResume] = useState<ResumeSnapshot | null>(null)
  const [storage, setStorage] = useState<StorageLocation[]>([])
  const [fasteners, setFasteners] = useState<Fastener[]>([])
  const [observations, setObservations] = useState<Observation[]>([])
  const [photos, setPhotos] = useState<Photo[]>([])
  const [events, setEvents] = useState<EventItem[]>([])
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [storageLabel, setStorageLabel] = useState('')
  const [storageNotes, setStorageNotes] = useState('')
  const [fastenerLabel, setFastenerLabel] = useState('')
  const [fastenerKind, setFastenerKind] = useState<'fastener' | 'small_part'>('fastener')
  const [fastenerOrigin, setFastenerOrigin] = useState('')
  const [targetStorageId, setTargetStorageId] = useState('')
  const [observationText, setObservationText] = useState('')
  const [observationCategory, setObservationCategory] = useState<(typeof OBSERVATION_CATEGORIES)[number]>('general')
  const [photoPurpose, setPhotoPurpose] = useState<(typeof PHOTO_PURPOSES)[number]>('current_step')
  const [photoFile, setPhotoFile] = useState<File | null>(null)

  const selectedSession = useMemo(() => sessions.find((session) => session.id === selectedId) || null, [sessions, selectedId])
  const canEdit = Boolean(resume?.lease.can_edit)
  const hardwareOut = fasteners.filter((item) => item.physical_state !== 'installed').length
  const hardwareStored = fasteners.filter((item) => item.physical_state === 'stored').length

  const loadSessions = useCallback(async () => {
    const rows = await apiRequest<RepairSession[]>('/api/v1/repair-sessions', undefined, { retryIdempotent: true })
    setSessions(rows)
    setSelectedId((current) => preferredRepairSessionId(rows, current))
  }, [])

  const loadMemory = useCallback(async (sessionId: string) => {
    if (!sessionId) {
      setResume(null)
      setStorage([])
      setFasteners([])
      setObservations([])
      setPhotos([])
      setEvents([])
      setTargetStorageId('')
      setActiveRepairSessionId(null)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const [resumeResult, storageResult, fastenerResult, observationResult, photoResult, eventResult] = await Promise.all([
        apiRequest<ResumeSnapshot>(
          `/api/v1/repair-sessions/${sessionId}/resume`,
          { headers: { 'X-PartGraph-Device-ID': repairDeviceId() } },
          { retryIdempotent: true },
        ),
        apiRequest<StorageLocation[]>(`/api/v1/repair-sessions/${sessionId}/storage-locations`, undefined, { retryIdempotent: true }),
        apiRequest<Fastener[]>(`/api/v1/repair-sessions/${sessionId}/fasteners`, undefined, { retryIdempotent: true }),
        apiRequest<Observation[]>(`/api/v1/repair-sessions/${sessionId}/observations`, undefined, { retryIdempotent: true }),
        apiRequest<Photo[]>(`/api/v1/repair-sessions/${sessionId}/photos`, undefined, { retryIdempotent: true }),
        loadEventHistory(sessionId),
      ])
      setResume(resumeResult)
      setStorage(storageResult)
      setFasteners(fastenerResult)
      setObservations(observationResult)
      setPhotos(photoResult)
      setEvents(eventResult)
      setTargetStorageId((current) => storageResult.some((location) => location.id === current) ? current : storageResult[0]?.id || '')
      setActiveRepairSessionId(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not load the repair log.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    loadSessions()
      .catch((failure) => setError(formatApiFailure(failure, 'Could not load repair sessions.')))
      .finally(() => setLoading(false))
  }, [loadSessions])
  useEffect(() => { void loadMemory(selectedId) }, [selectedId, loadMemory])

  function chooseSession(sessionId: string) {
    setSelectedId(sessionId)
    setActiveRepairSessionId(sessionId || null)
  }

  async function acquireLease(takeover = false) {
    if (!selectedId) return
    setBusy(true)
    setError(null)
    try {
      await apiRequest(`/api/v1/repair-sessions/${selectedId}/lease/${takeover ? 'takeover' : 'acquire'}`, { method: 'POST', headers: repairMutationHeaders() })
      await loadMemory(selectedId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not enable editing on this device.'))
    } finally {
      setBusy(false)
    }
  }

  async function createStorage(event: FormEvent) {
    event.preventDefault()
    if (!selectedId || !storageLabel.trim()) return
    setBusy(true)
    setError(null)
    try {
      await recoverableRepairMutation(
        selectedId,
        `/api/v1/repair-sessions/${selectedId}/storage-locations`,
        {
          method: 'POST',
          body: JSON.stringify({ label: storageLabel.trim(), notes: storageNotes.trim() || undefined }),
        },
        { json: true, prefix: 'storage_location' },
      )
      setStorageLabel('')
      setStorageNotes('')
      await loadMemory(selectedId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not add this storage location.'))
    } finally {
      setBusy(false)
    }
  }

  async function createFastener(event: FormEvent) {
    event.preventDefault()
    if (!selectedId || !fastenerLabel.trim()) return
    setBusy(true)
    setError(null)
    try {
      await recoverableRepairMutation(
        selectedId,
        `/api/v1/repair-sessions/${selectedId}/fasteners`,
        {
          method: 'POST',
          body: JSON.stringify({ kind: fastenerKind, label: fastenerLabel.trim(), origin: fastenerOrigin.trim() || undefined, physical_state: 'removed' }),
        },
        { json: true, prefix: 'fastener_record' },
      )
      setFastenerLabel('')
      setFastenerOrigin('')
      await loadMemory(selectedId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not record this hardware item.'))
    } finally {
      setBusy(false)
    }
  }

  async function updateFastener(fastener: Fastener, state: FastenerState) {
    if (!selectedId) return
    const storageId = state === 'stored' ? targetStorageId : undefined
    if (state === 'stored' && !storageId) {
      setError('Create and select a storage location before marking hardware as stored.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await recoverableRepairMutation(
        selectedId,
        `/api/v1/repair-sessions/${selectedId}/fasteners/${fastener.id}`,
        {
          method: 'PATCH',
          body: JSON.stringify({ physical_state: state, storage_location_id: storageId }),
        },
        { json: true, prefix: 'fastener_state' },
      )
      await loadMemory(selectedId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not update hardware state.'))
    } finally {
      setBusy(false)
    }
  }

  async function createObservation(event: FormEvent) {
    event.preventDefault()
    if (!selectedId || !observationText.trim()) return
    setBusy(true)
    setError(null)
    try {
      await recoverableRepairMutation(
        selectedId,
        `/api/v1/repair-sessions/${selectedId}/observations`,
        {
          method: 'POST',
          body: JSON.stringify({ category: observationCategory, text: observationText.trim() }),
        },
        { json: true, prefix: 'observation' },
      )
      setObservationText('')
      await loadMemory(selectedId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not save this note.'))
    } finally {
      setBusy(false)
    }
  }

  async function uploadPhoto(event: FormEvent) {
    event.preventDefault()
    if (!selectedId || !photoFile) return
    const body = new FormData()
    body.set('photo', photoFile)
    body.set('purpose', photoPurpose)
    setBusy(true)
    setError(null)
    try {
      await recoverableRepairMutation(
        selectedId,
        `/api/v1/repair-sessions/${selectedId}/photos`,
        { method: 'POST', body },
        { prefix: 'photo_add' },
      )
      setPhotoFile(null)
      await loadMemory(selectedId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not attach this photo.'))
    } finally {
      setBusy(false)
    }
  }

  async function deletePhoto(photoId: string) {
    if (!selectedId) return
    setBusy(true)
    setError(null)
    try {
      await recoverableRepairMutation(
        selectedId,
        `/api/v1/repair-sessions/${selectedId}/photos/${photoId}`,
        { method: 'DELETE' },
        { prefix: 'photo_delete' },
      )
      await loadMemory(selectedId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not remove this photo.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="repair-workspace-shell">
      <header className="workspace-hero">
        <p className="eyebrow">PARTGRAPH · REPAIR LOG</p>
        <h1>Remember where everything went and what you found.</h1>
        <p>Track removed hardware, storage locations, notes, and photos so the physical repair stays understandable from disassembly through reassembly.</p>
      </header>

      <section className="repair-panel panel">
        <div className="section-heading-row">
          <div><p className="eyebrow">CURRENT REPAIR</p><h2>{selectedSession?.title || 'Choose a repair'}</h2></div>
          {sessions.length > 0 && <select value={selectedId} onChange={(event) => chooseSession(event.target.value)}>{sessions.map((session) => <option key={session.id} value={session.id}>{session.title} · {session.status}</option>)}</select>}
        </div>
        {loading && <p className="muted">Loading repair log…</p>}
        {!loading && sessions.length === 0 && <div className="repair-empty"><h2>No repair available</h2><p>Start a repair first, then use this log to keep track of the physical work.</p></div>}
        {selectedId && resume && !canEdit && (
          <div className="lease-banner">
            <span>This repair is view-only on this device.</span>
            <button type="button" disabled={busy} onClick={() => void acquireLease(resume.lease.status === 'held_by_other')}>
              {resume.lease.status === 'held_by_other' ? 'Move editing here' : 'Edit this repair'}
            </button>
          </div>
        )}
        {error && <div className="workspace-alert workspace-alert--error">{error}</div>}
      </section>

      {selectedId && (
        <>
          <section className="repair-log-summary" aria-label="Repair memory summary">
            <article><span>Hardware tracked</span><strong>{fasteners.length}</strong><small>{hardwareOut} not installed</small></article>
            <article><span>Stored safely</span><strong>{hardwareStored}</strong><small>{storage.length} storage locations</small></article>
            <article><span>Repair notes</span><strong>{observations.length}</strong><small>Saved observations</small></article>
            <article><span>Photos</span><strong>{photos.length}</strong><small>Saved with this repair</small></article>
          </section>

          <div className="repair-dashboard-grid">
            <section className="repair-panel panel">
              <p className="eyebrow">STORAGE</p><h2>Where removed items are kept</h2>
              <form className="compact-form" onSubmit={(event) => void createStorage(event)}>
                <input disabled={!canEdit} value={storageLabel} placeholder="Location name" onChange={(event) => setStorageLabel(event.target.value)} />
                <input disabled={!canEdit} value={storageNotes} placeholder="Notes (optional)" onChange={(event) => setStorageNotes(event.target.value)} />
                <button disabled={!canEdit || busy}>Add location</button>
              </form>
              {storage.length > 0 && <label className="compact-form"><span>Store hardware in</span><select disabled={!canEdit || busy} value={targetStorageId} onChange={(event) => setTargetStorageId(event.target.value)}>{storage.map((location) => <option key={location.id} value={location.id}>{location.label}</option>)}</select></label>}
              <ul className="repair-list">{storage.map((location) => <li key={location.id}><strong>{location.label}</strong>{location.notes && <span>{location.notes}</span>}<small>{fasteners.filter((item) => item.storage_location_id === location.id).length} tracked items</small></li>)}</ul>
            </section>

            <section className="repair-panel panel repair-span-2">
              <p className="eyebrow">HARDWARE & SMALL PARTS</p><h2>What has been removed and where it is now</h2>
              <form className="compact-form compact-form--wide" onSubmit={(event) => void createFastener(event)}>
                <select disabled={!canEdit} value={fastenerKind} onChange={(event) => setFastenerKind(event.target.value as 'fastener' | 'small_part')}><option value="fastener">Fastener</option><option value="small_part">Small part</option></select>
                <input disabled={!canEdit} value={fastenerLabel} placeholder="Item label" onChange={(event) => setFastenerLabel(event.target.value)} />
                <input disabled={!canEdit} value={fastenerOrigin} placeholder="Origin / position" onChange={(event) => setFastenerOrigin(event.target.value)} />
                <button disabled={!canEdit || busy}>Record removed item</button>
              </form>
              {fasteners.length === 0 ? <p className="muted">No hardware recorded yet.</p> : <div className="hardware-grid">{fasteners.map((fastener) => <article key={fastener.id} className={`hardware-card hardware-card--${fastener.physical_state}`}><div><strong>{fastener.label}</strong><span>{human(fastener.kind)} · {human(fastener.physical_state)}</span>{fastener.origin && <small>{fastener.origin}</small>}</div><div className="repair-button-row"><button type="button" className="secondary" disabled={!canEdit || busy} onClick={() => void updateFastener(fastener, 'removed')}>Removed</button><button type="button" className="secondary" disabled={!canEdit || busy || !targetStorageId} onClick={() => void updateFastener(fastener, 'stored')}>Stored</button><button type="button" disabled={!canEdit || busy} onClick={() => void updateFastener(fastener, 'installed')}>Installed</button><button type="button" className="secondary" disabled={!canEdit || busy} onClick={() => void updateFastener(fastener, 'missing')}>Missing</button></div></article>)}</div>}
            </section>

            <section className="repair-panel panel">
              <p className="eyebrow">NOTES</p><h2>What you noticed</h2>
              <form className="compact-form" onSubmit={(event) => void createObservation(event)}>
                <select disabled={!canEdit} value={observationCategory} onChange={(event) => setObservationCategory(event.target.value as (typeof OBSERVATION_CATEGORIES)[number])}>{OBSERVATION_CATEGORIES.map((category) => <option key={category} value={category}>{human(category)}</option>)}</select>
                <textarea disabled={!canEdit} rows={3} maxLength={1000} value={observationText} placeholder="What did you observe?" onChange={(event) => setObservationText(event.target.value)} />
                <button disabled={!canEdit || busy}>Save note</button>
              </form>
              <ul className="repair-list">{observations.slice().reverse().slice(0, 12).map((observation) => <li key={observation.id}><strong>{human(observation.category)}</strong><span>{observation.text}</span><small>{new Date(observation.created_at).toLocaleString()}</small></li>)}</ul>
            </section>

            <section className="repair-panel panel">
              <p className="eyebrow">PHOTOS</p><h2>Visual repair memory</h2>
              <form className="compact-form" onSubmit={(event) => void uploadPhoto(event)}>
                <select disabled={!canEdit} value={photoPurpose} onChange={(event) => setPhotoPurpose(event.target.value as (typeof PHOTO_PURPOSES)[number])}>{PHOTO_PURPOSES.map((purpose) => <option key={purpose} value={purpose}>{human(purpose)}</option>)}</select>
                <input disabled={!canEdit} type="file" accept="image/*" onChange={(event) => setPhotoFile(event.target.files?.[0] || null)} />
                <button disabled={!canEdit || busy || !photoFile}>Attach photo</button>
              </form>
              {photos.length === 0 ? <p className="muted">No photos saved yet.</p> : (
                <div className="repair-photo-grid">
                  {photos.slice().reverse().slice(0, 12).map((photo) => (
                    <article className="repair-photo-card" key={photo.id}>
                      <img src={photo.content_url} alt={`${human(photo.purpose)} repair`} loading="lazy" />
                      <div><strong>{human(photo.purpose)}</strong><span>{new Date(photo.created_at).toLocaleString()}</span></div>
                      <button type="button" className="text-button" disabled={!canEdit || busy} onClick={() => void deletePhoto(photo.id)}>Delete</button>
                    </article>
                  ))}
                </div>
              )}
            </section>

            <section className="repair-panel panel repair-span-2">
              <p className="eyebrow">HISTORY</p><h2>What changed during this repair</h2>
              {events.length === 0 ? <p className="muted">No history recorded.</p> : <ol className="event-timeline">{events.slice().reverse().map((event) => <li key={event.id}><div><strong>{human(event.event_type)}</strong><small>{new Date(event.created_at).toLocaleString()}</small></div></li>)}</ol>}
            </section>
          </div>
        </>
      )}
    </main>
  )
}
