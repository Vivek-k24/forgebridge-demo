import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { apiRequest, CSRF_HEADERS, formatApiFailure } from './api'
import './garage-workspace.css'

type Resolution = 'matched' | 'ambiguous' | 'manual_candidate'
type VehicleBrand = { name: string; status: 'active' | 'legacy' }
type VehicleIdentity = {
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
}
type VehicleConfiguration = VehicleIdentity & {
  id: string
  verification_status: string
}
type SelectionResult = {
  resolution: Resolution
  normalized: VehicleIdentity
  matches: VehicleConfiguration[]
}
type VinDecodeResult = {
  source: 'provider' | 'cache'
  provider: string
  masked_vin: string
  observed_at: string
  expires_at: string
  resolution: Resolution
  identity: VehicleIdentity
  matches: VehicleConfiguration[]
}
type UserVehicle = {
  id: string
  nickname: string | null
  canonical_configuration_id: string | null
  identity_source: 'manual' | 'vin'
  identity_resolution: Resolution
  identity: VehicleIdentity
  masked_vin: string | null
  decoder_provider: string | null
  decoder_observed_at: string | null
  archived_at: string | null
  created_at: string
  updated_at: string
}
type VehicleProfile = {
  id: string
  vehicle_configuration_id: string
  profile_version: number
  verification_status: string
  source_match_count: number
  profile: Record<string, unknown>
  source_matrix: Record<string, unknown>
}
type ReconciliationField = {
  field: string
  kind: string
  status: string
  selected_value: unknown
  match_count: number
  sources: string[]
  conflicts: Array<{ value: unknown; match_count: number; sources: string[] }>
}
type Reconciliation = {
  summary: Record<string, number>
  fields: ReconciliationField[]
  observation_records: number
  independent_sources: number
}
type AddMode = 'manual' | 'vin'

const MIN_YEAR = 1996
const MAX_YEAR = new Date().getFullYear()

function optionPath(path: string, params: Record<string, string | number | undefined>) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') query.set(key, String(value))
  }
  const encoded = query.toString()
  return encoded ? `${path}?${encoded}` : path
}

function identityLine(identity: VehicleIdentity) {
  return [identity.year, identity.make, identity.model, identity.trim, identity.engine, identity.transmission, identity.drivetrain]
    .filter(Boolean)
    .join(' · ')
}

function resolutionLabel(resolution: Resolution) {
  if (resolution === 'matched') return 'Canonical configuration matched'
  if (resolution === 'ambiguous') return 'Multiple canonical variants remain'
  return 'Manual candidate'
}

function formatValue(value: unknown) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

export function GarageWorkspace({
  initialMarket = 'US',
  onStartRepair,
}: {
  initialMarket?: 'US' | 'CA'
  onStartRepair: (vehicleId: string) => void
}) {
  const [mode, setMode] = useState<AddMode>('manual')
  const [market, setMarket] = useState<'US' | 'CA'>(initialMarket)
  const [brands, setBrands] = useState<VehicleBrand[]>([])
  const [models, setModels] = useState<string[]>([])
  const [trims, setTrims] = useState<string[]>([])
  const [generations, setGenerations] = useState<string[]>([])
  const [year, setYear] = useState(Math.min(MAX_YEAR, 2009))
  const [make, setMake] = useState('Honda')
  const [model, setModel] = useState('Civic')
  const [trim, setTrim] = useState('Hybrid')
  const [generation, setGeneration] = useState('')
  const [manualNickname, setManualNickname] = useState('')
  const [selection, setSelection] = useState<SelectionResult | null>(null)
  const [manualBusy, setManualBusy] = useState(false)
  const [manualMessage, setManualMessage] = useState<string | null>(null)
  const [manualError, setManualError] = useState<string | null>(null)

  const [vin, setVin] = useState('')
  const [vinNickname, setVinNickname] = useState('')
  const [decode, setDecode] = useState<VinDecodeResult | null>(null)
  const [vinBusy, setVinBusy] = useState(false)
  const [vinMessage, setVinMessage] = useState<string | null>(null)
  const [vinError, setVinError] = useState<string | null>(null)

  const [vehicles, setVehicles] = useState<UserVehicle[]>([])
  const [showArchived, setShowArchived] = useState(false)
  const [vehiclesBusy, setVehiclesBusy] = useState(true)
  const [vehiclesError, setVehiclesError] = useState<string | null>(null)
  const [profileVehicleId, setProfileVehicleId] = useState<string | null>(null)
  const [profile, setProfile] = useState<VehicleProfile | null>(null)
  const [reconciliation, setReconciliation] = useState<Reconciliation | null>(null)
  const [profileBusy, setProfileBusy] = useState(false)
  const [profileError, setProfileError] = useState<string | null>(null)

  const knownMakes = useMemo(() => brands.map((brand) => brand.name), [brands])

  const loadVehicles = useCallback(async () => {
    setVehiclesBusy(true)
    setVehiclesError(null)
    try {
      const rows = await apiRequest<UserVehicle[]>(`/api/v1/user-vehicles${showArchived ? '?include_archived=true' : ''}`)
      setVehicles(rows)
    } catch (failure) {
      setVehicles([])
      setVehiclesError(formatApiFailure(failure, 'Could not load your garage.'))
    } finally {
      setVehiclesBusy(false)
    }
  }, [showArchived])

  useEffect(() => {
    void loadVehicles()
  }, [loadVehicles])

  useEffect(() => {
    let active = true
    apiRequest<VehicleBrand[]>('/api/v1/vehicle-brands', undefined, { retryIdempotent: true })
      .then((rows) => { if (active) setBrands(rows) })
      .catch(() => { if (active) setBrands([]) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    let active = true
    setModels([])
    if (!make.trim()) return () => { active = false }
    apiRequest<string[]>(optionPath('/api/v1/vehicle-options/models', { year, market, make: make.trim() }), undefined, { retryIdempotent: true })
      .then((rows) => { if (active) setModels(rows) })
      .catch(() => { if (active) setModels([]) })
    return () => { active = false }
  }, [year, market, make])

  useEffect(() => {
    let active = true
    setTrims([])
    setGenerations([])
    if (!make.trim() || !model.trim()) return () => { active = false }
    const base = { year, market, make: make.trim(), model: model.trim() }
    void Promise.all([
      apiRequest<string[]>(optionPath('/api/v1/vehicle-options/trims', base), undefined, { retryIdempotent: true }),
      apiRequest<string[]>(optionPath('/api/v1/vehicle-options/generations', base), undefined, { retryIdempotent: true }),
    ]).then(([trimRows, generationRows]) => {
      if (!active) return
      setTrims(trimRows)
      setGenerations(generationRows)
    }).catch(() => {
      if (!active) return
      setTrims([])
      setGenerations([])
    })
    return () => { active = false }
  }, [year, market, make, model])

  async function resolveManual(event: FormEvent) {
    event.preventDefault()
    setManualError(null)
    setManualMessage(null)
    setSelection(null)
    if (!make.trim() || !model.trim()) {
      setManualError('Make and model are required.')
      return
    }
    setManualBusy(true)
    try {
      const result = await apiRequest<SelectionResult>('/api/v1/vehicle-selection/resolve', {
        method: 'POST',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          year,
          market,
          make: make.trim(),
          model: model.trim(),
          trim: trim.trim() || undefined,
          generation: generation.trim() || undefined,
        }),
      })
      setSelection(result)
    } catch (failure) {
      setManualError(formatApiFailure(failure, 'Could not resolve these vehicle details.'))
    } finally {
      setManualBusy(false)
    }
  }

  async function saveManual() {
    if (!selection) return
    setManualBusy(true)
    setManualError(null)
    setManualMessage(null)
    try {
      const saved = await apiRequest<UserVehicle>('/api/v1/user-vehicles/manual', {
        method: 'POST',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nickname: manualNickname.trim() || undefined,
          selection: {
            year: selection.normalized.year,
            market: selection.normalized.market,
            make: selection.normalized.make,
            model: selection.normalized.model,
            trim: selection.normalized.trim || undefined,
            generation: selection.normalized.generation || undefined,
          },
        }),
      })
      setManualMessage(`Added ${saved.nickname || `${saved.identity.year} ${saved.identity.make} ${saved.identity.model}`} to your garage.`)
      setManualNickname('')
      await loadVehicles()
    } catch (failure) {
      setManualError(formatApiFailure(failure, 'Could not add this vehicle to your garage.'))
    } finally {
      setManualBusy(false)
    }
  }

  async function decodeVin(event: FormEvent) {
    event.preventDefault()
    setVinError(null)
    setVinMessage(null)
    setDecode(null)
    const normalized = vin.toUpperCase().replace(/\s/g, '')
    if (!/^[A-HJ-NPR-Z0-9]{17}$/.test(normalized)) {
      setVinError('VIN must contain 17 valid characters; I, O, and Q are not used.')
      return
    }
    setVinBusy(true)
    try {
      const result = await apiRequest<VinDecodeResult>('/api/v1/user-vehicles/vin/decode', {
        method: 'POST',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({ market, vin: normalized }),
      })
      setVin(normalized)
      setDecode(result)
    } catch (failure) {
      setVinError(formatApiFailure(failure, 'Could not decode this VIN.'))
    } finally {
      setVinBusy(false)
    }
  }

  async function saveVin() {
    if (!decode) return
    setVinBusy(true)
    setVinError(null)
    setVinMessage(null)
    try {
      const saved = await apiRequest<UserVehicle>('/api/v1/user-vehicles/vin', {
        method: 'POST',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({ market, vin, nickname: vinNickname.trim() || undefined }),
      })
      setVinMessage(`Added ${saved.nickname || `${saved.identity.year} ${saved.identity.make} ${saved.identity.model}`} to your garage.`)
      setVinNickname('')
      await loadVehicles()
    } catch (failure) {
      setVinError(formatApiFailure(failure, 'Could not add this VIN vehicle to your garage.'))
    } finally {
      setVinBusy(false)
    }
  }

  async function archiveVehicle(vehicleId: string) {
    setVehiclesError(null)
    try {
      await apiRequest(`/api/v1/user-vehicles/${vehicleId}/archive`, { method: 'PATCH', headers: CSRF_HEADERS })
      await loadVehicles()
    } catch (failure) {
      setVehiclesError(formatApiFailure(failure, 'Could not archive this vehicle.'))
    }
  }

  async function inspectVehicle(vehicle: UserVehicle) {
    if (!vehicle.canonical_configuration_id) return
    const configurationId = vehicle.canonical_configuration_id
    setProfileVehicleId(vehicle.id)
    setProfile(null)
    setReconciliation(null)
    setProfileError(null)
    setProfileBusy(true)
    try {
      const [profileResult, reconciliationResult] = await Promise.allSettled([
        apiRequest<VehicleProfile>(`/api/v1/vehicle-configurations/${configurationId}/profile`, undefined, { retryIdempotent: true }),
        apiRequest<Reconciliation>(`/api/v1/vehicle-configurations/${configurationId}/profile/reconciliation`, undefined, { retryIdempotent: true }),
      ])
      if (profileResult.status === 'fulfilled') setProfile(profileResult.value)
      if (reconciliationResult.status === 'fulfilled') setReconciliation(reconciliationResult.value)
      if (profileResult.status === 'rejected' && reconciliationResult.status === 'rejected') {
        setProfileError('No verified specification profile or reconciliation data is available for this configuration yet.')
      }
    } finally {
      setProfileBusy(false)
    }
  }

  return (
    <main className="garage-workspace">
      <header className="workspace-hero">
        <p className="eyebrow">PARTGRAPH · GARAGE</p>
        <h1>Add the vehicle first. Everything else follows its exact identity.</h1>
        <p>Use VIN evidence or manual vehicle details. Both paths save a private garage vehicle and preserve canonical verification boundaries.</p>
      </header>

      <section className="garage-add panel">
        <div className="segmented" role="tablist" aria-label="Add vehicle method">
          <button type="button" className={mode === 'manual' ? 'active' : ''} onClick={() => setMode('manual')}>Manual selection</button>
          <button type="button" className={mode === 'vin' ? 'active' : ''} onClick={() => setMode('vin')}>VIN</button>
        </div>

        {mode === 'manual' ? (
          <form className="garage-form" onSubmit={(event) => void resolveManual(event)}>
            <div className="garage-form-grid">
              <label><span>Year</span><input type="number" min={MIN_YEAR} max={MAX_YEAR} value={year} onChange={(event) => { setYear(Number(event.target.value)); setSelection(null) }} /></label>
              <label><span>Market</span><select value={market} onChange={(event) => { setMarket(event.target.value as 'US' | 'CA'); setSelection(null) }}><option value="US">United States</option><option value="CA">Canada</option></select></label>
              <label><span>Make</span><input list="garage-makes" value={make} onChange={(event) => { setMake(event.target.value); setSelection(null) }} /><datalist id="garage-makes">{knownMakes.map((item) => <option key={item} value={item} />)}</datalist></label>
              <label><span>Model</span><input list="garage-models" value={model} onChange={(event) => { setModel(event.target.value); setSelection(null) }} /><datalist id="garage-models">{models.map((item) => <option key={item} value={item} />)}</datalist></label>
              <label><span>Trim <small>optional</small></span><input list="garage-trims" value={trim} onChange={(event) => { setTrim(event.target.value); setSelection(null) }} /><datalist id="garage-trims">{trims.map((item) => <option key={item} value={item} />)}</datalist></label>
              <label><span>Generation <small>optional</small></span><input list="garage-generations" value={generation} onChange={(event) => { setGeneration(event.target.value); setSelection(null) }} /><datalist id="garage-generations">{generations.map((item) => <option key={item} value={item} />)}</datalist></label>
            </div>
            <button type="submit" disabled={manualBusy}>{manualBusy ? 'Resolving…' : 'Resolve vehicle'}</button>
            {manualError && <div className="workspace-alert workspace-alert--error">{manualError}</div>}
            {selection && (
              <div className="resolution-card">
                <div><p className="eyebrow">{selection.resolution.replace('_', ' ')}</p><h3>{resolutionLabel(selection.resolution)}</h3><p>{identityLine(selection.normalized)}</p>{selection.resolution === 'ambiguous' && <p className="muted">PartGraph will save the observed identity without guessing between canonical variants.</p>}</div>
                <label><span>Garage nickname <small>optional</small></span><input maxLength={80} value={manualNickname} placeholder="Daily Civic, project car…" onChange={(event) => setManualNickname(event.target.value)} /></label>
                <button type="button" disabled={manualBusy} onClick={() => void saveManual()}>{manualBusy ? 'Saving…' : 'Add to garage'}</button>
              </div>
            )}
            {manualMessage && <div className="workspace-alert workspace-alert--success">{manualMessage}</div>}
          </form>
        ) : (
          <form className="garage-form" onSubmit={(event) => void decodeVin(event)}>
            <div className="garage-form-grid garage-form-grid--vin">
              <label><span>Market</span><select value={market} onChange={(event) => { setMarket(event.target.value as 'US' | 'CA'); setDecode(null) }}><option value="US">United States</option><option value="CA">Canada</option></select></label>
              <label className="garage-vin-field"><span>17-character VIN</span><input value={vin} maxLength={17} autoCapitalize="characters" autoComplete="off" spellCheck={false} placeholder="1HGFA16589L000000" onChange={(event) => { setVin(event.target.value.toUpperCase()); setDecode(null); setVinMessage(null) }} /></label>
            </div>
            <button type="submit" disabled={vinBusy}>{vinBusy ? 'Decoding…' : 'Decode VIN'}</button>
            {vinError && <div className="workspace-alert workspace-alert--error">{vinError}</div>}
            {decode && (
              <div className="resolution-card">
                <div><p className="eyebrow">{decode.source === 'cache' ? 'CACHED VIN EVIDENCE' : 'VIN EVIDENCE'} · {decode.masked_vin}</p><h3>{resolutionLabel(decode.resolution)}</h3><p>{identityLine(decode.identity)}</p></div>
                <label><span>Garage nickname <small>optional</small></span><input maxLength={80} value={vinNickname} placeholder="Daily car, project car…" onChange={(event) => setVinNickname(event.target.value)} /></label>
                <button type="button" disabled={vinBusy} onClick={() => void saveVin()}>{vinBusy ? 'Saving…' : 'Add to garage'}</button>
              </div>
            )}
            {vinMessage && <div className="workspace-alert workspace-alert--success">{vinMessage}</div>}
          </form>
        )}
      </section>

      <section className="garage-list panel">
        <div className="section-heading-row"><div><p className="eyebrow">PRIVATE GARAGE</p><h2>Your vehicles</h2></div><label className="inline-check"><input type="checkbox" checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} />Include archived</label></div>
        {vehiclesBusy && <p className="muted">Loading garage…</p>}
        {vehiclesError && <div className="workspace-alert workspace-alert--error">{vehiclesError}</div>}
        {!vehiclesBusy && !vehiclesError && vehicles.length === 0 && <div className="empty-state"><strong>No saved vehicles yet.</strong><p>Add one above by VIN or manual selection.</p></div>}
        <div className="vehicle-card-list">
          {vehicles.map((vehicle) => (
            <article className={`vehicle-card ${vehicle.archived_at ? 'vehicle-card--archived' : ''}`} key={vehicle.id}>
              <div className="vehicle-card-main"><p className="eyebrow">{vehicle.identity_source.toUpperCase()} · {resolutionLabel(vehicle.identity_resolution)}</p><h3>{vehicle.nickname || `${vehicle.identity.year} ${vehicle.identity.make} ${vehicle.identity.model}`}</h3><p>{identityLine(vehicle.identity)}</p>{vehicle.masked_vin && <p className="muted">VIN {vehicle.masked_vin}</p>}</div>
              <div className="vehicle-card-actions">
                {!vehicle.archived_at && <button type="button" onClick={() => onStartRepair(vehicle.id)}>Start repair</button>}
                {vehicle.canonical_configuration_id && <button type="button" className="secondary" onClick={() => void inspectVehicle(vehicle)}>{profileVehicleId === vehicle.id ? 'Refresh specs' : 'View verified specs'}</button>}
                {!vehicle.archived_at && <button type="button" className="secondary" onClick={() => void archiveVehicle(vehicle.id)}>Archive</button>}
                {vehicle.archived_at && <span className="status-pill">Archived</span>}
              </div>
            </article>
          ))}
        </div>
      </section>

      {profileVehicleId && (
        <section className="vehicle-profile panel">
          <div className="section-heading-row"><div><p className="eyebrow">CANONICAL VEHICLE DATA</p><h2>Verified specification profile</h2></div><button type="button" className="secondary" onClick={() => { setProfileVehicleId(null); setProfile(null); setReconciliation(null); setProfileError(null) }}>Close</button></div>
          {profileBusy && <p className="muted">Loading profile and source reconciliation…</p>}
          {profileError && <div className="workspace-alert workspace-alert--error">{profileError}</div>}
          {profile && <div className="profile-summary"><span className="status-pill">{profile.verification_status}</span><span>Profile v{profile.profile_version}</span><span>{profile.source_match_count} matching sources</span></div>}
          {profile && <pre className="profile-json">{JSON.stringify(profile.profile, null, 2)}</pre>}
          {reconciliation && (
            <div className="reconciliation-block">
              <div className="profile-summary"><span>{reconciliation.independent_sources} independent sources</span><span>{reconciliation.observation_records} reviewed records</span>{Object.entries(reconciliation.summary).map(([key, value]) => <span key={key}>{key.replaceAll('_', ' ')}: {value}</span>)}</div>
              <div className="reconciliation-table" role="table" aria-label="Vehicle specification reconciliation">
                {reconciliation.fields.map((field) => <div className="reconciliation-row" role="row" key={field.field}><strong>{field.field}</strong><span>{field.status}</span><span>{formatValue(field.selected_value)}</span><span>{field.match_count} vote{field.match_count === 1 ? '' : 's'}</span><span>{field.sources.join(', ') || '—'}</span>{field.conflicts.length > 0 && <small>Conflicts: {field.conflicts.map((conflict) => `${formatValue(conflict.value)} (${conflict.sources.join(', ')})`).join(' · ')}</small>}</div>)}
              </div>
            </div>
          )}
        </section>
      )}
    </main>
  )
}
