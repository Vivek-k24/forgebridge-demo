import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { apiRequest, CSRF_HEADERS, formatApiFailure } from './api'
import './user-vehicles.css'

type Resolution = 'matched' | 'ambiguous' | 'manual_candidate'

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

export type ManualSelection = {
  resolution: Resolution
  normalized: {
    year: number
    market: string
    make: string
    model: string
    trim: string | null
    generation: string | null
  }
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

const VEHICLE_CHANGE_EVENT = 'partgraph:user-vehicles-changed'

function identityLine(identity: VehicleIdentity): string {
  return [
    identity.year,
    identity.make,
    identity.model,
    identity.trim,
    identity.engine,
    identity.transmission,
    identity.drivetrain,
  ].filter(Boolean).join(' · ')
}

function resolutionLabel(resolution: Resolution): string {
  if (resolution === 'matched') return 'Known canonical configuration'
  if (resolution === 'ambiguous') return 'Multiple canonical variants remain'
  return 'Private manual candidate'
}

export function SaveManualVehicle({ selection }: { selection: ManualSelection }) {
  const [nickname, setNickname] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function saveVehicle() {
    setSaving(true)
    setMessage(null)
    setError(null)
    try {
      const saved = await apiRequest<UserVehicle>('/api/v1/user-vehicles/manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...CSRF_HEADERS },
        body: JSON.stringify({
          nickname: nickname.trim() || undefined,
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
      setMessage(`Saved ${saved.nickname || `${saved.identity.year} ${saved.identity.make} ${saved.identity.model}`}.`)
      window.dispatchEvent(new Event(VEHICLE_CHANGE_EVENT))
    } catch (requestError) {
      setError(formatApiFailure(requestError, 'Could not save this vehicle.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="save-manual">
      <label>
        <span className="field-label-row"><span>Garage nickname</span><small>optional</small></span>
        <input
          value={nickname}
          maxLength={80}
          placeholder="Daily Civic, project car…"
          onChange={(event) => setNickname(event.target.value)}
        />
      </label>
      <button type="button" onClick={() => void saveVehicle()} disabled={saving}>
        {saving ? 'Saving…' : 'Save to my vehicles'}
      </button>
      {message && <p className="inline-success">{message}</p>}
      {error && <p className="inline-error">{error}</p>}
    </div>
  )
}

export function UserVehicleWorkspace({
  initialMarket,
  onUseDetails,
}: {
  initialMarket: 'US' | 'CA'
  onUseDetails: () => void
}) {
  const [market, setMarket] = useState<'US' | 'CA'>(initialMarket)
  const [vin, setVin] = useState('')
  const [nickname, setNickname] = useState('')
  const [decoding, setDecoding] = useState(false)
  const [saving, setSaving] = useState(false)
  const [decode, setDecode] = useState<VinDecodeResult | null>(null)
  const [vinError, setVinError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const [vehicles, setVehicles] = useState<UserVehicle[]>([])
  const [loadingVehicles, setLoadingVehicles] = useState(true)
  const [vehiclesError, setVehiclesError] = useState<string | null>(null)
  const [showArchived, setShowArchived] = useState(false)

  const loadVehicles = useCallback(async () => {
    setLoadingVehicles(true)
    setVehiclesError(null)
    try {
      const query = showArchived ? '?include_archived=true' : ''
      const items = await apiRequest<UserVehicle[]>(`/api/v1/user-vehicles${query}`)
      setVehicles(items)
    } catch (requestError) {
      setVehicles([])
      setVehiclesError(formatApiFailure(requestError, 'Could not load your vehicles.'))
    } finally {
      setLoadingVehicles(false)
    }
  }, [showArchived])

  useEffect(() => {
    void loadVehicles()
  }, [loadVehicles])

  useEffect(() => {
    const refresh = () => void loadVehicles()
    window.addEventListener(VEHICLE_CHANGE_EVENT, refresh)
    return () => window.removeEventListener(VEHICLE_CHANGE_EVENT, refresh)
  }, [loadVehicles])

  async function decodeVin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalized = vin.toUpperCase().replace(/\s/g, '')
    setDecode(null)
    setSaveMessage(null)
    setVinError(null)
    if (!/^[A-HJ-NPR-Z0-9]{17}$/.test(normalized)) {
      setVinError('VIN must contain 17 valid characters; I, O, and Q are not used.')
      return
    }

    setDecoding(true)
    try {
      const result = await apiRequest<VinDecodeResult>('/api/v1/user-vehicles/vin/decode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...CSRF_HEADERS },
        body: JSON.stringify({ market, vin: normalized }),
      })
      setVin(normalized)
      setDecode(result)
    } catch (requestError) {
      setVinError(formatApiFailure(requestError, 'Could not decode this VIN.'))
    } finally {
      setDecoding(false)
    }
  }

  async function saveVinVehicle() {
    if (!decode) return
    setSaving(true)
    setSaveMessage(null)
    setVinError(null)
    try {
      const saved = await apiRequest<UserVehicle>('/api/v1/user-vehicles/vin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...CSRF_HEADERS },
        body: JSON.stringify({
          market,
          vin,
          nickname: nickname.trim() || undefined,
        }),
      })
      setSaveMessage(`Saved ${saved.nickname || `${saved.identity.year} ${saved.identity.make} ${saved.identity.model}`}.`)
      setNickname('')
      window.dispatchEvent(new Event(VEHICLE_CHANGE_EVENT))
    } catch (requestError) {
      setVinError(formatApiFailure(requestError, 'Could not save this VIN vehicle.'))
    } finally {
      setSaving(false)
    }
  }

  async function archiveVehicle(vehicleId: string) {
    setVehiclesError(null)
    try {
      await apiRequest<UserVehicle>(`/api/v1/user-vehicles/${vehicleId}/archive`, {
        method: 'PATCH',
        headers: CSRF_HEADERS,
      })
      await loadVehicles()
    } catch (requestError) {
      setVehiclesError(formatApiFailure(requestError, 'Could not archive this vehicle.'))
    }
  }

  return (
    <div className="private-vehicle-workspace">
      <div className="section-heading">
        <div>
          <p className="eyebrow">TAB 02 · VIN</p>
          <h2>VIN search</h2>
        </div>
        <span className="trust-badge">private vehicle data</span>
      </div>
      <p className="hint">
        PartGraph validates the VIN first, asks NHTSA for identity evidence, then checks that evidence
        against PartGraph’s current canonical vehicle records. The full VIN is never placed in shared
        canonical data.
      </p>

      <form className="vin-form vin-form--live" onSubmit={(event) => void decodeVin(event)}>
        <label>
          <span className="field-label-row"><span>Market</span><small>required</small></span>
          <select
            value={market}
            onChange={(event) => {
              setMarket(event.target.value as 'US' | 'CA')
              setDecode(null)
              setVinError(null)
            }}
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
            spellCheck={false}
            placeholder="1HGCM82633A004352"
            onChange={(event) => {
              setVin(event.target.value.toUpperCase())
              setDecode(null)
              setVinError(null)
              setSaveMessage(null)
            }}
          />
        </label>
        <button type="submit" disabled={decoding}>
          {decoding ? 'Decoding…' : 'Decode VIN'}
        </button>
      </form>

      {vinError && (
        <div className="result-card result-card--error vin-fallback">
          <p>{vinError}</p>
          <button type="button" className="secondary" onClick={onUseDetails}>Use vehicle details instead</button>
        </div>
      )}

      {decode && (
        <div className={`result-card result-card--${decode.resolution} vin-result`}>
          <div className="vin-result__headline">
            <div>
              <p className="eyebrow">VIN RESOLUTION · {decode.source === 'cache' ? 'CACHED EVIDENCE' : 'NHTSA EVIDENCE'}</p>
              <h3>{resolutionLabel(decode.resolution)}</h3>
            </div>
            <span className="masked-vin">{decode.masked_vin}</span>
          </div>
          <p>{identityLine(decode.identity)}</p>
          {decode.resolution === 'ambiguous' && (
            <p className="muted">The decoder narrowed the vehicle down, but PartGraph will not guess between the remaining canonical variants.</p>
          )}
          {decode.resolution === 'manual_candidate' && (
            <p className="muted">No canonical row matches this observation yet. Saving keeps the identity private to your garage and does not change shared mechanical truth.</p>
          )}
          <div className="vin-save-row">
            <label>
              <span className="field-label-row"><span>Garage nickname</span><small>optional</small></span>
              <input
                value={nickname}
                maxLength={80}
                placeholder="Daily car, project wagon…"
                onChange={(event) => setNickname(event.target.value)}
              />
            </label>
            <button type="button" onClick={() => void saveVinVehicle()} disabled={saving}>
              {saving ? 'Saving…' : 'Save to my vehicles'}
            </button>
          </div>
          {saveMessage && <p className="inline-success">{saveMessage}</p>}
        </div>
      )}

      <section className="garage" aria-live="polite">
        <div className="garage__heading">
          <div>
            <p className="eyebrow">PRIVATE GARAGE</p>
            <h3>Your vehicles</h3>
          </div>
          <label className="archive-toggle">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(event) => setShowArchived(event.target.checked)}
            />
            Include archived
          </label>
        </div>

        {loadingVehicles && <p className="muted">Loading your vehicles…</p>}
        {vehiclesError && <div className="result-card result-card--error">{vehiclesError}</div>}
        {!loadingVehicles && !vehiclesError && vehicles.length === 0 && (
          <div className="garage__empty">
            <strong>No saved vehicles yet.</strong>
            <p>Decode a VIN here or save a resolved vehicle from Vehicle details.</p>
          </div>
        )}
        <div className="garage__list">
          {vehicles.map((vehicle) => (
            <article className={`garage-card ${vehicle.archived_at ? 'garage-card--archived' : ''}`} key={vehicle.id}>
              <div>
                <p className="eyebrow">{vehicle.identity_source === 'vin' ? 'VIN VEHICLE' : 'DETAILS VEHICLE'}</p>
                <h4>{vehicle.nickname || `${vehicle.identity.year} ${vehicle.identity.make} ${vehicle.identity.model}`}</h4>
                <p>{identityLine(vehicle.identity)}</p>
                <p className="garage-card__meta">
                  {resolutionLabel(vehicle.identity_resolution)}
                  {vehicle.masked_vin ? ` · ${vehicle.masked_vin}` : ''}
                </p>
              </div>
              {vehicle.archived_at ? (
                <span className="archived-badge">Archived</span>
              ) : (
                <button type="button" className="secondary" onClick={() => void archiveVehicle(vehicle.id)}>
                  Archive
                </button>
              )}
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
