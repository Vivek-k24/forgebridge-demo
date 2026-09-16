import { useEffect, useMemo, useState } from 'react'
import { apiRequest, CSRF_HEADERS, formatApiFailure } from './api'
import './equipment-inventory.css'

type Category = { key: string; label: string; visual_key: string; total_count: number; inventory_count: number }
type Item = { id: string; catalog_key: string; category: string; name: string; visual_key: string; in_inventory: boolean; quantity: number | null }
type Page = { category: string; query: string; total: number; offset: number; limit: number; items: Item[] }
type SpeechAlternative = { transcript: string }
type SpeechResult = { 0?: SpeechAlternative }
type SpeechEvent = { results?: { 0?: SpeechResult } }
type Recognition = { lang: string; continuous: boolean; interimResults: boolean; start(): void; onresult: ((event: SpeechEvent) => void) | null; onerror: (() => void) | null; onend: (() => void) | null }
type RecognitionCtor = new () => Recognition

const PAGE_SIZE = 100
const GLYPHS: Record<string, string> = { wrench: 'W', socket: 'S', ratchet: 'R', extension: 'E', screwdriver: 'D', bit: 'B', hex: 'H', pliers: 'P', power: 'PWR', light: 'L', jack: 'J', stand: 'ST', ramp: 'RP', drill: 'DR', oil: 'OIL', fluid: 'FL', coolant: 'CLT', 'washer-fluid': 'WSH', lug: 'LUG', fastener: 'F', bolt: 'BT', nut: 'N', washer: 'WS', clip: 'CL', rivet: 'RV', hose: 'HS', oring: 'O', measure: 'M', shop: 'SH', specialty: 'SP', other: 'OT' }

function recognitionCtor(): RecognitionCtor | null {
  const value = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }
  return value.SpeechRecognition ?? value.webkitSpeechRecognition ?? null
}

export function EquipmentInventoryWorkspace() {
  const [categories, setCategories] = useState<Category[]>([])
  const [category, setCategory] = useState('')
  const [query, setQuery] = useState('')
  const [items, setItems] = useState<Item[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [busy, setBusy] = useState<Set<string>>(new Set())
  const [listening, setListening] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const ownedCount = useMemo(() => categories.reduce((sum, row) => sum + row.inventory_count, 0), [categories])

  async function loadCatalog(nextCategory: string, nextQuery: string, offset = 0, append = false) {
    if (!nextCategory) return
    try {
      setCatalogLoading(true)
      setError(null)
      const params = new URLSearchParams({ category: nextCategory, q: nextQuery, offset: String(offset), limit: String(PAGE_SIZE) })
      const page = await apiRequest<Page>(`/api/v1/equipment/catalog?${params.toString()}`, undefined, { retryIdempotent: true })
      setItems((current) => append ? [...current, ...page.items] : page.items)
      setTotal(page.total)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not load the inventory catalog.'))
      if (!append) { setItems([]); setTotal(0) }
    } finally {
      setCatalogLoading(false)
    }
  }

  useEffect(() => {
    let active = true
    apiRequest<Category[]>('/api/v1/equipment/categories', undefined, { retryIdempotent: true })
      .then((rows) => { if (active) setCategories(rows) })
      .catch((failure) => { if (active) setError(formatApiFailure(failure, 'Could not load inventory categories.')) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!category) return
    const timer = window.setTimeout(() => void loadCatalog(category, query), 250)
    return () => window.clearTimeout(timer)
  }, [category, query])

  function chooseCategory(next: string) {
    setCategory(next)
    setQuery('')
    setItems([])
    setTotal(0)
    setMessage(null)
    setError(null)
  }

  async function toggle(item: Item, checked: boolean) {
    if (busy.has(item.id)) return
    setBusy((current) => new Set(current).add(item.id))
    setError(null)
    try {
      const updated = await apiRequest<Item>(`/api/v1/equipment/inventory/${item.id}`, {
        method: 'PUT',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({ in_inventory: checked, quantity: item.quantity ?? 1 }),
      })
      setItems((current) => current.map((row) => row.id === item.id ? updated : row))
      setCategories((current) => current.map((row) => row.key !== item.category || item.in_inventory === checked ? row : { ...row, inventory_count: Math.max(0, row.inventory_count + (checked ? 1 : -1)) }))
      setMessage(checked ? `${item.name} added to inventory.` : `${item.name} removed from inventory.`)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not update your inventory.'))
    } finally {
      setBusy((current) => { const next = new Set(current); next.delete(item.id); return next })
    }
  }

  function voiceSearch() {
    if (!category || listening) return
    const Constructor = recognitionCtor()
    if (!Constructor) { setMessage('Voice search is not supported by this browser.'); return }
    const recognition = new Constructor()
    recognition.lang = 'en-US'
    recognition.continuous = false
    recognition.interimResults = false
    recognition.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript?.trim()
      if (transcript) setQuery(transcript)
    }
    recognition.onerror = () => { setListening(false); setMessage('Voice search could not hear a search term.') }
    recognition.onend = () => setListening(false)
    setListening(true)
    recognition.start()
  }

  if (loading) return <main className="equipment-shell"><p className="muted">Loading inventory…</p></main>

  return <main className="equipment-shell">
    <header className="equipment-heading">
      <div><p className="eyebrow">PARTGRAPH · INVENTORY</p><h1>Tools, fluids & supplies</h1><p>Choose a category, find what you own, and check it once.</p></div>
      <div className="equipment-owned-count"><strong>{ownedCount}</strong><span>in your inventory</span></div>
    </header>
    {error && <div className="workspace-alert workspace-alert--error">{error}</div>}
    {message && <div className="workspace-alert workspace-alert--success" aria-live="polite">{message}</div>}
    <section className="equipment-controls panel">
      <label><span>Category</span><select value={category} onChange={(event) => chooseCategory(event.target.value)}><option value="">Choose a category</option>{categories.map((row) => <option key={row.key} value={row.key}>{row.label} · {row.total_count}</option>)}</select></label>
      <label><span>Search inventory</span><div className="equipment-search-box"><span aria-hidden="true">⌕</span><input type="search" value={query} disabled={!category} placeholder={category ? 'Search this category' : 'Choose a category first'} onChange={(event) => setQuery(event.target.value)} /><button type="button" disabled={!category} className={listening ? 'equipment-mic active' : 'equipment-mic'} aria-label="Search inventory by voice" title="Search by voice" onClick={voiceSearch}><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 3a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Z" /><path d="M5.5 10.5v.5a6.5 6.5 0 0 0 13 0v-.5M12 17.5V21M9 21h6" /></svg></button></div></label>
    </section>
    {!category ? <section className="equipment-empty panel"><h2>Select a category to begin.</h2><p>Search turns on after a category is selected.</p></section> : <section className="equipment-catalog panel">
      <div className="equipment-list-heading"><div><p className="eyebrow">CATALOG</p><h2>{categories.find((row) => row.key === category)?.label}</h2></div><span>{total} items</span></div>
      <div className="equipment-table" role="table" aria-label="Inventory catalog">
        <div className="equipment-table-row equipment-table-header" role="row"><div role="columnheader">Add to inventory</div><div role="columnheader">Inventory item</div></div>
        {items.map((item) => <div className={item.in_inventory ? 'equipment-table-row owned' : 'equipment-table-row'} role="row" key={item.id}><div className="equipment-check-cell" role="cell"><input type="checkbox" checked={item.in_inventory} disabled={busy.has(item.id)} aria-label={`${item.in_inventory ? 'Remove' : 'Add'} ${item.name}`} onChange={(event) => void toggle(item, event.target.checked)} /></div><div className="equipment-name-cell" role="cell"><span className="equipment-visual" aria-hidden="true">{GLYPHS[item.visual_key] ?? 'I'}</span><strong>{item.name}</strong>{item.in_inventory && <span className="equipment-owned-pill">In inventory</span>}</div></div>)}
      </div>
      {catalogLoading && items.length === 0 && <p className="muted equipment-loading">Searching inventory…</p>}
      {!catalogLoading && items.length === 0 && <div className="equipment-no-results">No matching items in this category.</div>}
      {items.length < total && <button type="button" className="secondary equipment-load-more" disabled={catalogLoading} onClick={() => void loadCatalog(category, query, items.length, true)}>{catalogLoading ? 'Loading…' : `Load more · ${total - items.length} remaining`}</button>}
    </section>}
  </main>
}
