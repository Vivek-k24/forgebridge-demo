import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { apiRequest, formatApiFailure } from './api'
import { repairMutationHeaders } from './repair-client'
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

const OBSERVATION_CATEGORIES = ['general','condition','damage','part_number','before','after','removed_part','current_step'] as const
const PHOTO_PURPOSES = ['current_step','removed_part','fastener','damage','part_number','before','after','general'] as const

export function RepairLogWorkspace() {
  const [sessions, setSessions] = useState<RepairSession[]>([])
  const [selectedId, setSelectedId] = useState(() => window.sessionStorage.getItem('partgraph:active-repair-session') || '')
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
  const [observationText, setObservationText] = useState('')
  const [observationCategory, setObservationCategory] = useState<(typeof OBSERVATION_CATEGORIES)[number]>('general')
  const [photoPurpose, setPhotoPurpose] = useState<(typeof PHOTO_PURPOSES)[number]>('current_step')
  const [photoFile, setPhotoFile] = useState<File | null>(null)

  const selectedSession = useMemo(() => sessions.find((session) => session.id === selectedId) || null, [sessions, selectedId])
  const canEdit = Boolean(resume?.lease.can_edit)

  const loadSessions = useCallback(async () => {
    const rows = await apiRequest<RepairSession[]>('/api/v1/repair-sessions', undefined, { retryIdempotent: true })
    setSessions(rows)
    setSelectedId((current) => current && rows.some((row) => row.id === current) ? current : rows[0]?.id || '')
  }, [])

  const loadMemory = useCallback(async (sessionId: string) => {
    if (!sessionId) {
      setResume(null); setStorage([]); setFasteners([]); setObservations([]); setPhotos([]); setEvents([])
      return
    }
    setLoading(true)
    setError(null)
    try {
      const [resumeResult, storageResult, fastenerResult, observationResult, photoResult, eventResult] = await Promise.all([
        apiRequest<ResumeSnapshot>(`/api/v1/repair-sessions/${sessionId}/resume`, undefined, { retryIdempotent: true }),
        apiRequest<StorageLocation[]>(`/api/v1/repair-sessions/${sessionId}/storage-locations`, undefined, { retryIdempotent: true }),
        apiRequest<Fastener[]>(`/api/v1/repair-sessions/${sessionId}/fasteners`, undefined, { retryIdempotent: true }),
        apiRequest<Observation[]>(`/api/v1/repair-sessions/${sessionId}/observations`, undefined, { retryIdempotent: true }),
        apiRequest<Photo[]>(`/api/v1/repair-sessions/${sessionId}/photos`, undefined, { retryIdempotent: true }),
        apiRequest<EventPage>(`/api/v1/repair-sessions/${sessionId}/events?limit=100`, undefined, { retryIdempotent: true }),
      ])
      setResume(resumeResult)
      setStorage(storageResult)
      setFasteners(fastenerResult)
      setObservations(observationResult)
      setPhotos(photoResult)
      setEvents(eventResult.items)
      window.sessionStorage.setItem('partgraph:active-repair-session', sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not load repair memory.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    loadSessions().catch((failure) => setError(formatApiFailure(failure, 'Could not load repair sessions.'))).finally(() => setLoading(false))
  }, [loadSessions])
  useEffect(() => { void loadMemory(selectedId) }, [selectedId, loadMemory])

  async function acquireLease(takeover = false) {
    if (!selectedId) return
    setBusy(true); setError(null)
    try {
      await apiRequest(`/api/v1/repair-sessions/${selectedId}/lease/${takeover ? 'takeover' : 'acquire'}`, { method: 'POST', headers: repairMutationHeaders() })
      await loadMemory(selectedId)
    } catch (failure) { setError(formatApiFailure(failure, 'Could not obtain the repair edit lease.')) }
    finally { setBusy(false) }
  }

  async function createStorage(event: FormEvent) {
    event.preventDefault(); if (!selectedId || !storageLabel.trim()) return
    setBusy(true); setError(null)
    try {
      await apiRequest(`/api/v1/repair-sessions/${selectedId}/storage-locations`, { method: 'POST', headers: repairMutationHeaders({ json: true }), body: JSON.stringify({ label: storageLabel.trim(), notes: storageNotes.trim() || undefined }) })
      setStorageLabel(''); setStorageNotes(''); await loadMemory(selectedId)
    } catch (failure) { setError(formatApiFailure(failure, 'Could not add this storage location.')) }
    finally { setBusy(false) }
  }

  async function createFastener(event: FormEvent) {
    event.preventDefault(); if (!selectedId || !fastenerLabel.trim()) return
    setBusy(true); setError(null)
    try {
      await apiRequest(`/api/v1/repair-sessions/${selectedId}/fasteners`, { method: 'POST', headers: repairMutationHeaders({ json: true }), body: JSON.stringify({ kind: fastenerKind, label: fastenerLabel.trim(), origin: fastenerOrigin.trim() || undefined, physical_state: 'removed' }) })
      setFastenerLabel(''); setFastenerOrigin(''); await loadMemory(selectedId)
    } catch (failure) { setError(formatApiFailure(failure, 'Could not record this fastener or small part.')) }
    finally { setBusy(false) }
  }

  async function updateFastener(fastener: Fastener, state: FastenerState) {
    if (!selectedId) return
    const storageId = state === 'stored' ? storage[0]?.id : undefined
    if (state === 'stored' && !storageId) { setError('Create a storage location before marking hardware as stored.'); return }
    setBusy(true); setError(null)
    try {
      await apiRequest(`/api/v1/repair-sessions/${selectedId}/fasteners/${fastener.id}`, { method: 'PATCH', headers: repairMutationHeaders({ json: true }), body: JSON.stringify({ physical_state: state, storage_location_id: storageId }) })
      await loadMemory(selectedId)
    } catch (failure) { setError(formatApiFailure(failure, 'Could not update hardware state.')) }
    finally { setBusy(false) }
  }

  async function createObservation(event: FormEvent) {
    event.preventDefault(); if (!selectedId || !observationText.trim()) return
    setBusy(true); setError(null)
    try {
      await apiRequest(`/api/v1/repair-sessions/${selectedId}/observations`, { method: 'POST', headers: repairMutationHeaders({ json: true }), body: JSON.stringify({ category: observationCategory, text: observationText.trim() }) })
      setObservationText(''); await loadMemory(selectedId)
    } catch (failure) { setError(formatApiFailure(failure, 'Could not record this observation.')) }
    finally { setBusy(false) }
  }

  async function uploadPhoto(event: FormEvent) {
    event.preventDefault(); if (!selectedId || !photoFile) return
    const body = new FormData(); body.set('photo', photoFile); body.set('purpose', photoPurpose)
    setBusy(true); setError(null)
    try {
      await apiRequest(`/api/v1/repair-sessions/${selectedId}/photos`, { method: 'POST', headers: repairMutationHeaders(), body })
      setPhotoFile(null); await loadMemory(selectedId)
    } catch (failure) { setError(formatApiFailure(failure, 'Could not attach this photo.')) }
    finally { setBusy(false) }
  }

  async function deletePhoto(photoId: string) {
    if (!selectedId) return
    setBusy(true); setError(null)
    try {
      await apiRequest(`/api/v1/repair-sessions/${selectedId}/photos/${photoId}`, { method: 'DELETE', headers: repairMutationHeaders() })
      await loadMemory(selectedId)
    } catch (failure) { setError(formatApiFailure(failure, 'Could not remove this photo evidence.')) }
    finally { setBusy(false) }
  }

  return (
    <main className="repair-workspace-shell">
      <header className="workspace-hero"><p className="eyebrow">PARTGRAPH · REPAIR LOG</p><h1>Track the physical repair, not just the procedure.</h1><p>Storage locations, fasteners, small parts, observations, photo evidence, and the append-only event timeline all live here.</p></header>
      <section className="repair-panel panel">
        <div className="section-heading-row"><div><p className="eyebrow">SESSION</p><h2>{selectedSession?.title || 'Choose a repair'}</h2></div>{sessions.length > 0 && <select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>{sessions.map((session) => <option key={session.id} value={session.id}>{session.title} · {session.status}</option>)}</select>}</div>
        {loading && <p className="muted">Loading repair memory…</p>}
        {!loading && sessions.length === 0 && <div className="repair-empty"><h2>No repair session available</h2><p>Start a repair first, then use this log throughout disassembly, diagnosis, replacement, and reassembly.</p></div>}
        {selectedId && resume && !canEdit && <div className="lease-banner"><span>This device does not currently hold the edit lease.</span><button type="button" disabled={busy} onClick={() => void acquireLease(resume.lease.status === 'held_by_other')}>{resume.lease.status === 'held_by_other' ? 'Take over lease' : 'Acquire edit lease'}</button></div>}
        {error && <div className="workspace-alert workspace-alert--error">{error}</div>}
      </section>

      {selectedId && (
        <div className="repair-dashboard-grid">
          <section className="repair-panel panel">
            <p className="eyebrow">STORAGE</p><h2>Hardware locations</h2>
            <form className="compact-form" onSubmit={(event) => void createStorage(event)}><input disabled={!canEdit} value={storageLabel} placeholder="Passenger tray, bag A…" onChange={(event) => setStorageLabel(event.target.value)} /><input disabled={!canEdit} value={storageNotes} placeholder="Notes (optional)" onChange={(event) => setStorageNotes(event.target.value)} /><button disabled={!canEdit || busy}>Add location</button></form>
            <ul className="repair-list">{storage.map((location) => <li key={location.id}><strong>{location.label}</strong>{location.notes && <span>{location.notes}</span>}<small>{fasteners.filter((item) => item.storage_location_id === location.id).length} tracked items</small></li>)}</ul>
          </section>

          <section className="repair-panel panel repair-span-2">
            <p className="eyebrow">FASTENERS & SMALL PARTS</p><h2>Physical state</h2>
            <form className="compact-form compact-form--wide" onSubmit={(event) => void createFastener(event)}><select disabled={!canEdit} value={fastenerKind} onChange={(event) => setFastenerKind(event.target.value as 'fastener' | 'small_part')}><option value="fastener">Fastener</option><option value="small_part">Small part</option></select><input disabled={!canEdit} value={fastenerLabel} placeholder="Upper support 10 mm bolt" onChange={(event) => setFastenerLabel(event.target.value)} /><input disabled={!canEdit} value={fastenerOrigin} placeholder="Origin / position" onChange={(event) => setFastenerOrigin(event.target.value)} /><button disabled={!canEdit || busy}>Record removed item</button></form>
            {fasteners.length === 0 ? <p className="muted">No hardware recorded yet.</p> : <div className="hardware-grid">{fasteners.map((fastener) => <article key={fastener.id} className="hardware-card"><div><strong>{fastener.label}</strong><span>{fastener.kind.replace('_', ' ')} · {fastener.physical_state}</span>{fastener.origin && <small>{fastener.origin}</small>}</div><div className="repair-button-row"><button type="button" className="secondary" disabled={!canEdit || busy} onClick={() => void updateFastener(fastener, 'removed')}>Removed</button><button type="button" className="secondary" disabled={!canEdit || busy || storage.length === 0} onClick={() => void updateFastener(fastener, 'stored')}>Stored</button><button type="button" disabled={!canEdit || busy} onClick={() => void updateFastener(fastener, 'installed')}>Installed</button><button type="button" className="secondary" disabled={!canEdit || busy} onClick={() => void updateFastener(fastener, 'missing')}>Missing</button></div></article>)}</div>}
          </section>

          <section className="repair-panel panel">
            <p className="eyebrow">OBSERVATIONS</p><h2>Repair notes</h2>
            <form className="compact-form" onSubmit={(event) => void createObservation(event)}><select disabled={!canEdit} value={observationCategory} onChange={(event) => setObservationCategory(event.target.value as (typeof OBSERVATION_CATEGORIES)[number])}>{OBSERVATION_CATEGORIES.map((category) => <option key={category} value={category}>{category.replaceAll('_', ' ')}</option>)}</select><textarea disabled={!canEdit} rows={3} maxLength={1000} value={observationText} placeholder="What did you observe?" onChange={(event) => setObservationText(event.target.value)} /><button disabled={!canEdit || busy}>Record observation</button></form>
            <ul className="repair-list">{observations.slice().reverse().slice(0, 12).map((observation) => <li key={observation.id}><strong>{observation.category.replaceAll('_', ' ')}</strong><span>{observation.text}</span><small>{observation.source} · {observation.review_state}</small></li>)}</ul>
          </section>

          <section className="repair-panel panel">
            <p className="eyebrow">PHOTO EVIDENCE</p><h2>Before, after, damage, parts</h2>
            <form className="compact-form" onSubmit={(event) => void uploadPhoto(event)}><select disabled={!canEdit} value={photoPurpose} onChange={(event) => setPhotoPurpose(event.target.value as (typeof PHOTO_PURPOSES)[number])}>{PHOTO_PURPOSES.map((purpose) => <option key={purpose} value={purpose}>{purpose.replaceAll('_', ' ')}</option>)}</select><input disabled={!canEdit} type="file" accept="image/*" onChange={(event) => setPhotoFile(event.target.files?.[0] || null)} /><button disabled={!canEdit || busy || !photoFile}>Attach photo</button></form>
            <ul className="repair-list">{photos.slice().reverse().slice(0, 12).map((photo) => <li key={photo.id}><strong>{photo.purpose.replaceAll('_', ' ')}</strong><span>{photo.original_filename || photo.media_type} · {Math.max(1, Math.round(photo.byte_size / 1024))} KB</span><button type="button" className="text-button" disabled={!canEdit || busy} onClick={() => void deletePhoto(photo.id)}>Delete</button></li>)}</ul>
          </section>

          <section className="repair-panel panel repair-span-2">
            <p className="eyebrow">APPEND-ONLY TIMELINE</p><h2>Session events</h2>
            {events.length === 0 ? <p className="muted">No events recorded.</p> : <ol className="event-timeline">{events.slice().reverse().map((event) => <li key={event.id}><span>#{event.sequence}</span><div><strong>{event.event_type.replaceAll('_', ' ')}</strong><small>{new Date(event.created_at).toLocaleString()}</small></div></li>)}</ol>}
          </section>
        </div>
      )}
    </main>
  )
}
