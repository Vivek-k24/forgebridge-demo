import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type PointerEvent,
  type WheelEvent,
} from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const HARD_TIMEOUT_MS = 10_000
const MIN_SUPPORTED_YEAR = 1996
const MAX_SUPPORTED_YEAR = new Date().getFullYear()
const DEFAULT_YEAR = Math.min(MAX_SUPPORTED_YEAR, Math.max(MIN_SUPPORTED_YEAR, 2015))

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
  verification_status: string
}

type VehicleBrand = {
  name: string
  status: 'active' | 'legacy'
}

type SelectionResult = {
  resolution: 'matched' | 'ambiguous' | 'manual_candidate'
  normalized: {
    year: number
    market: string
    make: string
    model: string
    trim: string | null
    generation: string | null
  }
  matches: VehicleConfiguration[]
}

type VehicleForm = {
  year: number
  market: 'US' | 'CA'
  make: string
  model: string
  trim: string
  generation: string
}

type SearchComboProps = {
  label: string
  value: string
  options: string[]
  placeholder: string
  disabled?: boolean
  optional?: boolean
  allowManual?: boolean
  loading?: boolean
  onChange: (value: string) => void
  onSelect: (value: string) => void
}

const EMPTY_FORM: VehicleForm = {
  year: DEFAULT_YEAR,
  market: 'US',
  make: '',
  model: '',
  trim: '',
  generation: '',
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
        // Preserve the HTTP status when the response has no JSON body.
      }
      throw new Error(message)
    }
    return (await response.json()) as T
  } finally {
    window.clearTimeout(timeout)
  }
}

function optionPath(path: string, params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value))
  })
  return `${path}?${search.toString()}`
}

function YearWheel({ value, onChange }: { value: number; onChange: (year: number) => void }) {
  const pointerStart = useRef<number | null>(null)
  const clamp = (year: number) => Math.min(MAX_SUPPORTED_YEAR, Math.max(MIN_SUPPORTED_YEAR, year))
  const setYear = (year: number) => onChange(clamp(year))
  const offsets = [2, 1, 0, -1, -2]

  function onWheel(event: WheelEvent<HTMLDivElement>) {
    if (document.activeElement !== event.currentTarget) return
    event.preventDefault()
    if (Math.abs(event.deltaY) < 4) return
    setYear(value - Math.sign(event.deltaY))
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      setYear(value + 1)
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setYear(value - 1)
    }
    if (event.key === 'Home') {
      event.preventDefault()
      setYear(MAX_SUPPORTED_YEAR)
    }
    if (event.key === 'End') {
      event.preventDefault()
      setYear(MIN_SUPPORTED_YEAR)
    }
  }

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    event.currentTarget.focus()
    pointerStart.current = event.clientY
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  function onPointerUp(event: PointerEvent<HTMLDivElement>) {
    if (pointerStart.current === null) return
    const delta = event.clientY - pointerStart.current
    pointerStart.current = null
    if (Math.abs(delta) < 24) return
    const steps = Math.max(-4, Math.min(4, Math.round(delta / 38)))
    setYear(value + steps)
  }

  return (
    <div className="year-field">
      <div className="field-label-row">
        <span>Year</span>
        <small>{MIN_SUPPORTED_YEAR}–{MAX_SUPPORTED_YEAR}</small>
      </div>
      <div
        className="year-wheel"
        role="spinbutton"
        aria-label="Vehicle model year"
        aria-valuemin={MIN_SUPPORTED_YEAR}
        aria-valuemax={MAX_SUPPORTED_YEAR}
        aria-valuenow={value}
        tabIndex={0}
        onWheel={onWheel}
        onKeyDown={onKeyDown}
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
      >
        <div className="year-wheel__selection" />
        {offsets.map((offset) => {
          const year = value + offset
          const available = year >= MIN_SUPPORTED_YEAR && year <= MAX_SUPPORTED_YEAR
          return (
            <button
              className={`year-wheel__item year-wheel__item--${Math.abs(offset)}`}
              key={offset}
              type="button"
              tabIndex={-1}
              disabled={!available}
              aria-hidden={offset !== 0}
              onClick={(event) => {
                event.stopPropagation()
                if (available) setYear(year)
              }}
            >
              {available ? year : ''}
            </button>
          )
        })}
      </div>
      <p className="field-note">Focus and scroll, use a trackpad, or swipe/drag the wheel.</p>
    </div>
  )
}

function SearchCombo({
  label,
  value,
  options,
  placeholder,
  disabled = false,
  optional = false,
  allowManual = true,
  loading = false,
  onChange,
  onSelect,
}: SearchComboProps) {
  const [open, setOpen] = useState(false)
  const normalized = value.trim().toLocaleLowerCase()
  const exact = options.some((option) => option.toLocaleLowerCase() === normalized)
  const showManual = allowManual && normalized.length > 0 && !exact

  return (
    <label className="combo-field">
      <span className="field-label-row">
        <span>{label}</span>
        {optional && <small>optional</small>}
      </span>
      <div className={`combo ${disabled ? 'combo--disabled' : ''}`}>
        <input
          value={value}
          disabled={disabled}
          placeholder={placeholder}
          autoComplete="off"
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          onChange={(event) => {
            onChange(event.target.value)
            setOpen(true)
          }}
        />
        <span className="combo__glyph" aria-hidden="true">⌄</span>
        {open && !disabled && (
          <div className="combo__menu" role="listbox">
            {loading && <div className="combo__status">Searching known configurations…</div>}
            {!loading && options.map((option) => (
              <button
                type="button"
                role="option"
                aria-selected={option.toLocaleLowerCase() === normalized}
                className="combo__option"
                key={option}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  onSelect(option)
                  setOpen(false)
                }}
              >
                {option}
              </button>
            ))}
            {!loading && showManual && (
              <button
                type="button"
                className="combo__option combo__option--manual"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => setOpen(false)}
              >
                Use “{value.trim()}” as a manual candidate
              </button>
            )}
            {!loading && options.length === 0 && !showManual && (
              <div className="combo__status">No known options for this selection yet.</div>
            )}
          </div>
        )}
      </div>
    </label>
  )
}

function App() {
  const [runtime, setRuntime] = useState<RuntimeState>({ status: 'checking' })
  const [tab, setTab] = useState<'details' | 'vin'>('details')
  const [form, setForm] = useState<VehicleForm>(EMPTY_FORM)
  const [brands, setBrands] = useState<VehicleBrand[]>([])
  const [modelOptions, setModelOptions] = useState<string[]>([])
  const [trimOptions, setTrimOptions] = useState<string[]>([])
  const [generationOptions, setGenerationOptions] = useState<string[]>([])
  const [modelLoading, setModelLoading] = useState(false)
  const [trimLoading, setTrimLoading] = useState(false)
  const [generationLoading, setGenerationLoading] = useState(false)
  const [resolving, setResolving] = useState(false)
  const [selection, setSelection] = useState<SelectionResult | null>(null)
  const [selectionError, setSelectionError] = useState<string | null>(null)
  const [vin, setVin] = useState('')
  const [vinMessage, setVinMessage] = useState<string | null>(null)

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

  useEffect(() => {
    void checkRuntime()
    void apiRequest<VehicleBrand[]>('/api/v1/vehicle-brands').then(setBrands)
  }, [checkRuntime])

  useEffect(() => {
    setSelection(null)
    if (!form.make) {
      setModelOptions([])
      return
    }
    let active = true
    const timer = window.setTimeout(() => {
      setModelLoading(true)
      void apiRequest<string[]>(
        optionPath('/api/v1/vehicle-options/models', {
          year: form.year,
          market: form.market,
          make: form.make,
          q: form.model || undefined,
        }),
      ).then((items) => {
        if (active) setModelOptions(items)
      }).catch(() => {
        if (active) setModelOptions([])
      }).finally(() => {
        if (active) setModelLoading(false)
      })
    }, 180)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [form.make, form.market, form.model, form.year])

  useEffect(() => {
    setSelection(null)
    if (!form.make || !form.model) {
      setTrimOptions([])
      return
    }
    let active = true
    const timer = window.setTimeout(() => {
      setTrimLoading(true)
      void apiRequest<string[]>(
        optionPath('/api/v1/vehicle-options/trims', {
          year: form.year,
          market: form.market,
          make: form.make,
          model: form.model,
          q: form.trim || undefined,
        }),
      ).then((items) => {
        if (active) setTrimOptions(items)
      }).catch(() => {
        if (active) setTrimOptions([])
      }).finally(() => {
        if (active) setTrimLoading(false)
      })
    }, 180)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [form.make, form.market, form.model, form.trim, form.year])

  useEffect(() => {
    setSelection(null)
    if (!form.make || !form.model) {
      setGenerationOptions([])
      return
    }
    let active = true
    const timer = window.setTimeout(() => {
      setGenerationLoading(true)
      void apiRequest<string[]>(
        optionPath('/api/v1/vehicle-options/generations', {
          year: form.year,
          market: form.market,
          make: form.make,
          model: form.model,
          trim: form.trim || undefined,
          q: form.generation || undefined,
        }),
      ).then((items) => {
        if (active) setGenerationOptions(items)
      }).catch(() => {
        if (active) setGenerationOptions([])
      }).finally(() => {
        if (active) setGenerationLoading(false)
      })
    }, 180)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [form.generation, form.make, form.market, form.model, form.trim, form.year])

  function resetDependentFields(level: 'year' | 'market' | 'make' | 'model' | 'trim', value: string | number) {
    setForm((current) => {
      if (level === 'year') return { ...EMPTY_FORM, year: Number(value), market: current.market }
      if (level === 'market') return { ...EMPTY_FORM, year: current.year, market: value as 'US' | 'CA' }
      if (level === 'make') return { ...current, make: String(value), model: '', trim: '', generation: '' }
      if (level === 'model') return { ...current, model: String(value), trim: '', generation: '' }
      return { ...current, trim: String(value), generation: '' }
    })
    setSelection(null)
    setSelectionError(null)
  }

  async function resolveVehicle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!form.make || !form.model.trim()) return
    setResolving(true)
    setSelection(null)
    setSelectionError(null)
    try {
      const result = await apiRequest<SelectionResult>('/api/v1/vehicle-selection/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          year: form.year,
          market: form.market,
          make: form.make,
          model: form.model,
          trim: form.trim.trim() || undefined,
          generation: form.generation.trim() || undefined,
        }),
      })
      setSelection(result)
    } catch (error) {
      setSelectionError(error instanceof Error ? error.message : 'Could not check this vehicle.')
    } finally {
      setResolving(false)
    }
  }

  function validateVin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalized = vin.toUpperCase().replace(/\s/g, '')
    if (!/^[A-HJ-NPR-Z0-9]{17}$/.test(normalized)) {
      setVinMessage('VIN must contain 17 valid characters; I, O, and Q are not used.')
      return
    }
    setVinMessage('VIN format is valid. Decode wiring arrives with the private UserVehicle/auth block.')
  }

  const activeBrands = brands.filter((brand) => brand.status === 'active')
  const legacyBrands = brands.filter((brand) => brand.status === 'legacy')

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">PARTGRAPH · VEHICLE IDENTITY</p>
        <h1>Identify the vehicle.</h1>
        <p className="lede">
          Select a known configuration or enter what you know. Manual text is searched, normalized,
          and kept out of shared canonical truth unless later evidence verifies it.
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
        <button
          type="button"
          className="secondary"
          onClick={() => void checkRuntime()}
          disabled={runtime.status === 'checking'}
        >
          Check again
        </button>
      </section>

      <section className="workspace panel">
        <div className="tabs" role="tablist" aria-label="Vehicle identification method">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'details'}
            className={tab === 'details' ? 'tab tab--active' : 'tab'}
            onClick={() => setTab('details')}
          >
            Vehicle details
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'vin'}
            className={tab === 'vin' ? 'tab tab--active' : 'tab'}
            onClick={() => setTab('vin')}
          >
            VIN search
          </button>
        </div>

        {tab === 'details' && (
          <div className="tab-content" role="tabpanel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">TAB 01 · SELECT</p>
                <h2>Vehicle details</h2>
              </div>
              <span className="trust-badge">read-only canonical search</span>
            </div>

            <form className="vehicle-selector" onSubmit={(event) => void resolveVehicle(event)}>
              <YearWheel
                value={form.year}
                onChange={(year) => resetDependentFields('year', year)}
              />

              <div className="selector-fields">
                <label>
                  <span className="field-label-row"><span>Market</span><small>required</small></span>
                  <select
                    value={form.market}
                    onChange={(event) => resetDependentFields('market', event.target.value)}
                  >
                    <option value="US">United States</option>
                    <option value="CA">Canada</option>
                  </select>
                </label>

                <label>
                  <span className="field-label-row"><span>Make</span><small>required</small></span>
                  <select
                    required
                    value={form.make}
                    onChange={(event) => resetDependentFields('make', event.target.value)}
                  >
                    <option value="">Select make</option>
                    <optgroup label="Active">
                      {activeBrands.map((brand) => (
                        <option key={brand.name} value={brand.name}>{brand.name}</option>
                      ))}
                    </optgroup>
                    <optgroup label="Legacy / used fleet">
                      {legacyBrands.map((brand) => (
                        <option key={brand.name} value={brand.name}>{brand.name}</option>
                      ))}
                    </optgroup>
                  </select>
                </label>

                <SearchCombo
                  label="Model"
                  value={form.model}
                  options={modelOptions}
                  placeholder={form.make ? 'Search model…' : 'Choose make first'}
                  disabled={!form.make}
                  loading={modelLoading}
                  onChange={(value) => resetDependentFields('model', value)}
                  onSelect={(value) => resetDependentFields('model', value)}
                />

                <SearchCombo
                  label="Trim"
                  value={form.trim}
                  options={trimOptions}
                  placeholder={form.model ? 'Search trim…' : 'Choose model first'}
                  disabled={!form.model}
                  optional
                  loading={trimLoading}
                  onChange={(value) => resetDependentFields('trim', value)}
                  onSelect={(value) => resetDependentFields('trim', value)}
                />

                <SearchCombo
                  label="Generation"
                  value={form.generation}
                  options={generationOptions}
                  placeholder={form.model ? 'Search generation…' : 'Choose model first'}
                  disabled={!form.model}
                  optional
                  loading={generationLoading}
                  onChange={(value) => setForm((current) => ({ ...current, generation: value }))}
                  onSelect={(value) => setForm((current) => ({ ...current, generation: value }))}
                />
              </div>

              <div className="selector-action">
                <button type="submit" disabled={resolving || !form.make || !form.model.trim()}>
                  {resolving ? 'Checking…' : 'Check vehicle'}
                </button>
                <p>Generation is retained as supporting metadata and does not decide fitment here.</p>
              </div>
            </form>

            {selectionError && <div className="result-card result-card--error">{selectionError}</div>}
            {selection && (
              <div className={`result-card result-card--${selection.resolution}`}>
                <p className="eyebrow">RESOLUTION</p>
                {selection.resolution === 'matched' && <h3>Known configuration found.</h3>}
                {selection.resolution === 'ambiguous' && <h3>More than one canonical variant matches.</h3>}
                {selection.resolution === 'manual_candidate' && <h3>Manual candidate — canonical database unchanged.</h3>}
                <p>
                  {selection.normalized.year} · {selection.normalized.market} · {selection.normalized.make} · {selection.normalized.model}
                  {selection.normalized.trim ? ` · ${selection.normalized.trim}` : ''}
                </p>
                {selection.resolution === 'ambiguous' && (
                  <p className="muted">Exact fitment will require more verified detail later. PartGraph will not guess between variants.</p>
                )}
                {selection.resolution === 'manual_candidate' && (
                  <p className="muted">The typed value was searched but not promoted into shared mechanical truth.</p>
                )}
              </div>
            )}
          </div>
        )}

        {tab === 'vin' && (
          <div className="tab-content" role="tabpanel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">TAB 02 · VIN</p>
                <h2>VIN search</h2>
              </div>
              <span className="trust-badge">private vehicle data</span>
            </div>
            <p className="hint">
              VIN decoding will normalize NHTSA vehicle identity through the same PartGraph resolver.
              Full VINs will never be stored in shared canonical vehicle records.
            </p>
            <form className="vin-form" onSubmit={validateVin}>
              <label>
                <span className="field-label-row"><span>Market</span><small>required</small></span>
                <select
                  value={form.market}
                  onChange={(event) => setForm((current) => ({ ...current, market: event.target.value as 'US' | 'CA' }))}
                >
                  <option value="US">United States</option>
                  <option value="CA">Canada</option>
                </select>
              </label>
              <label className="vin-input">
                <span className="field-label-row"><span>17-character VIN</span><small>private</small></span>
                <input
                  value={vin}
                  maxLength={17}
                  autoCapitalize="characters"
                  autoComplete="off"
                  placeholder="1HGFA16569L…"
                  onChange={(event) => {
                    setVin(event.target.value.toUpperCase())
                    setVinMessage(null)
                  }}
                />
              </label>
              <button type="submit">Validate VIN</button>
            </form>
            {vinMessage && <div className="result-card">{vinMessage}</div>}
          </div>
        )}
      </section>
    </main>
  )
}

export default App
