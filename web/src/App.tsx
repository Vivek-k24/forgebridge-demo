import { useCallback, useEffect, useState, type FormEvent } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const HARD_TIMEOUT_MS = 10_000

type RuntimeState =
  | { status: 'checking' }
  | { status: 'ready'; requestMs: number; databaseMs: number }
  | { status: 'unavailable'; message: string }

type VehicleConfiguration = {
  id: string
  year: number
  market: string
  make: string
  model: string
  generation: string | null
  trim: string | null
  body_style: string | null
  engine: string | null
  transmission: string | null
  drivetrain: string | null
  identity_source: string
  verification_status: string
  created_at: string
}

type VehicleConfigurationResult = {
  created: boolean
  resolution: 'created' | 'matched' | 'enriched'
  configuration: VehicleConfiguration
}

type VehicleForm = {
  year: string
  market: string
  make: string
  model: string
  generation: string
  trim: string
  body_style: string
  engine: string
  transmission: string
  drivetrain: string
}

const EMPTY_FORM: VehicleForm = {
  year: '',
  market: '',
  make: '',
  model: '',
  generation: '',
  trim: '',
  body_style: '',
  engine: '',
  transmission: '',
  drivetrain: '',
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), HARD_TIMEOUT_MS)

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
    })
    if (!response.ok) {
      let message = `API returned ${response.status}`
      try {
        const payload = (await response.json()) as { detail?: string }
        if (payload.detail) message = payload.detail
      } catch {
        // Keep the HTTP status message when the response is not JSON.
      }
      throw new Error(message)
    }
    return (await response.json()) as T
  } finally {
    window.clearTimeout(timeout)
  }
}

function optional(value: string): string | undefined {
  const cleaned = value.trim()
  return cleaned || undefined
}

function App() {
  const [runtime, setRuntime] = useState<RuntimeState>({ status: 'checking' })
  const [form, setForm] = useState<VehicleForm>(EMPTY_FORM)
  const [configurations, setConfigurations] = useState<VehicleConfiguration[]>([])
  const [saving, setSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const [listError, setListError] = useState<string | null>(null)

  const checkRuntime = useCallback(async () => {
    setRuntime({ status: 'checking' })
    const started = performance.now()

    try {
      const payload = await apiRequest<{ database_ms: number }>('/api/v1/health/ready')
      setRuntime({
        status: 'ready',
        requestMs: Math.round(performance.now() - started),
        databaseMs: payload.database_ms,
      })
    } catch (error) {
      const message = error instanceof DOMException && error.name === 'AbortError'
        ? 'Hard 10-second boundary reached.'
        : 'Interactive runtime is unavailable.'
      setRuntime({ status: 'unavailable', message })
    }
  }, [])

  const loadConfigurations = useCallback(async () => {
    try {
      const items = await apiRequest<VehicleConfiguration[]>('/api/v1/vehicle-configurations?limit=20')
      setConfigurations(items)
      setListError(null)
    } catch (error) {
      setListError(error instanceof Error ? error.message : 'Could not load configurations.')
    }
  }, [])

  useEffect(() => {
    void checkRuntime()
    void loadConfigurations()
  }, [checkRuntime, loadConfigurations])

  function updateField(field: keyof VehicleForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function saveConfiguration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setSaveMessage(null)

    const payload = {
      year: Number(form.year),
      market: form.market,
      make: form.make,
      model: form.model,
      generation: optional(form.generation),
      trim: optional(form.trim),
      body_style: optional(form.body_style),
      engine: optional(form.engine),
      transmission: optional(form.transmission),
      drivetrain: optional(form.drivetrain),
    }

    try {
      const result = await apiRequest<VehicleConfigurationResult>('/api/v1/vehicle-configurations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const messages = {
        created: `Saved configuration ${result.configuration.id}.`,
        matched: `Matched existing configuration ${result.configuration.id}.`,
        enriched: `Updated existing configuration ${result.configuration.id} with the new details.`,
      }
      setSaveMessage(messages[result.resolution])
      setForm(EMPTY_FORM)
      await loadConfigurations()
    } catch (error) {
      setSaveMessage(error instanceof Error ? error.message : 'Could not save configuration.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">PARTGRAPH · BLOCK 2</p>
        <h1>Vehicle identity</h1>
        <p className="lede">
          Persist an exact configuration before any parts, assemblies, or repair state can depend on it.
        </p>
      </header>

      <section className="runtime-card" aria-live="polite">
        <span className={`dot dot--${runtime.status}`} />
        <div>
          <strong>
            {runtime.status === 'checking' && 'Checking runtime…'}
            {runtime.status === 'ready' && 'Interactive runtime ready'}
            {runtime.status === 'unavailable' && 'Runtime unavailable'}
          </strong>
          {runtime.status === 'ready' && (
            <p>Round trip {runtime.requestMs} ms · PostgreSQL {runtime.databaseMs} ms</p>
          )}
          {runtime.status === 'unavailable' && <p>{runtime.message}</p>}
        </div>
        <button type="button" className="secondary" onClick={() => void checkRuntime()} disabled={runtime.status === 'checking'}>
          Check again
        </button>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">MANUAL IDENTITY INPUT</p>
            <h2>Save a configuration</h2>
          </div>
          <span className="trust-badge">unverified until evidence-backed</span>
        </div>
        <p className="hint">
          Compatible partial entries enrich one record. Conflicting or ambiguous identities are never merged automatically.
        </p>

        <form className="vehicle-form" onSubmit={(event) => void saveConfiguration(event)}>
          <label>Year<input required inputMode="numeric" min="1886" max="2100" value={form.year} onChange={(event) => updateField('year', event.target.value)} /></label>
          <label>Market<input required placeholder="US" value={form.market} onChange={(event) => updateField('market', event.target.value)} /></label>
          <label>Make<input required placeholder="Honda" value={form.make} onChange={(event) => updateField('make', event.target.value)} /></label>
          <label>Model<input required placeholder="Civic" value={form.model} onChange={(event) => updateField('model', event.target.value)} /></label>
          <label>Generation<input placeholder="Optional" value={form.generation} onChange={(event) => updateField('generation', event.target.value)} /></label>
          <label>Trim<input placeholder="Optional" value={form.trim} onChange={(event) => updateField('trim', event.target.value)} /></label>
          <label>Body style<input placeholder="Optional" value={form.body_style} onChange={(event) => updateField('body_style', event.target.value)} /></label>
          <label>Engine<input placeholder="Optional" value={form.engine} onChange={(event) => updateField('engine', event.target.value)} /></label>
          <label>Transmission<input placeholder="Optional" value={form.transmission} onChange={(event) => updateField('transmission', event.target.value)} /></label>
          <label>Drivetrain<input placeholder="Optional" value={form.drivetrain} onChange={(event) => updateField('drivetrain', event.target.value)} /></label>

          <div className="form-actions">
            <button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save configuration'}</button>
            {saveMessage && <p className="save-message">{saveMessage}</p>}
          </div>
        </form>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">POSTGRESQL</p>
            <h2>Stored configurations</h2>
          </div>
          <strong>{configurations.length}</strong>
        </div>

        {listError && <p className="error-message">{listError}</p>}
        {!listError && configurations.length === 0 && (
          <p className="empty-state">No vehicle configurations stored yet.</p>
        )}
        <div className="configuration-list">
          {configurations.map((item) => (
            <article className="configuration" key={item.id}>
              <div>
                <strong>{item.year} {item.make} {item.model}</strong>
                <p>{[item.trim, item.body_style, item.engine, item.transmission].filter(Boolean).join(' · ') || 'Base identity only'}</p>
              </div>
              <div className="configuration-meta">
                <span>{item.market}</span>
                <span>{item.verification_status}</span>
                <code>{item.id.slice(0, 8)}</code>
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  )
}

export default App
