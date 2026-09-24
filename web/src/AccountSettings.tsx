import { useEffect, useState } from 'react'
import { apiRequest, CSRF_HEADERS, formatApiFailure } from './api'
import { applyTextScale, readTextScale, TEXT_SCALE_OPTIONS, type TextScalePercent } from './ui-preferences'
import './account-settings.css'

type UnitPreference = 'us_customary' | 'metric'
type User = {
  id: string
  email: string
  username: string
  created_at: string
}
type AuthResult = { user: User }
type PreferenceRead = { units: UnitPreference }

function unitLabel(units: UnitPreference): string {
  return units === 'metric' ? 'Metric' : 'US customary'
}

export function AccountSettingsWorkspace() {
  const [user, setUser] = useState<User | null>(null)
  const [units, setUnits] = useState<UnitPreference | null>(null)
  const [textScale, setTextScale] = useState<TextScalePercent>(() => readTextScale())
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    async function load() {
      try {
        setLoading(true)
        setError(null)
        const [auth, preference] = await Promise.all([
          apiRequest<AuthResult>('/api/v1/auth/me'),
          apiRequest<PreferenceRead>('/api/v1/account/preferences'),
        ])
        if (!active) return
        setUser(auth.user)
        setUnits(preference.units)
      } catch (failure) {
        if (active) setError(formatApiFailure(failure, 'Could not load account settings.'))
      } finally {
        if (active) setLoading(false)
      }
    }
    void load()
    return () => { active = false }
  }, [])

  async function changeUnits(next: UnitPreference) {
    if (next === units) return
    try {
      setBusy(true)
      setError(null)
      setMessage(null)
      const preference = await apiRequest<PreferenceRead>('/api/v1/account/preferences', {
        method: 'PATCH',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({ units: next }),
      })
      setUnits(preference.units)
      window.dispatchEvent(new CustomEvent('partgraph:preferences-changed', { detail: preference }))
      setMessage(`Measurement units changed to ${unitLabel(preference.units)}.`)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not save account settings.'))
    } finally {
      setBusy(false)
    }
  }

  function changeTextScale(next: TextScalePercent) {
    setTextScale(next)
    applyTextScale(next)
    setError(null)
    setMessage(`Text size changed to ${next}%.`)
  }

  return (
    <main className="settings-shell">
      <header className="workspace-hero settings-heading">
        <p className="eyebrow">PARTGRAPH · SETTINGS</p>
        <h1>Account and display settings</h1>
        <p>Adjust PartGraph for this account and the screen you are using.</p>
      </header>

      {error && <div className="workspace-alert workspace-alert--error">{error}</div>}
      {message && <div className="workspace-alert workspace-alert--success">{message}</div>}
      {loading ? <p className="muted">Loading settings…</p> : (
        <div className="settings-grid">
          <section className="panel settings-panel">
            <p className="eyebrow">ACCOUNT</p>
            <h2>Signed-in identity</h2>
            {user && (
              <dl className="settings-identity">
                <div><dt>Username</dt><dd>@{user.username}</dd></div>
                <div><dt>Email</dt><dd>{user.email}</dd></div>
                <div><dt>Account created</dt><dd>{new Date(user.created_at).toLocaleDateString()}</dd></div>
              </dl>
            )}
          </section>

          <section className="panel settings-panel">
            <p className="eyebrow">MEASUREMENTS</p>
            <h2>Units</h2>
            <p className="muted">Choose how supported measurements are displayed.</p>
            <fieldset className="settings-radio-fieldset">
              <legend>Measurement units</legend>
              <div className="settings-choice-grid">
                <label className={units === 'us_customary' ? 'settings-choice settings-choice--active' : 'settings-choice'}>
                  <input
                    type="radio"
                    name="measurement-units"
                    value="us_customary"
                    checked={units === 'us_customary'}
                    disabled={busy}
                    onChange={() => void changeUnits('us_customary')}
                  />
                  <strong>US customary</strong>
                  <span>Use US customary measurements.</span>
                </label>
                <label className={units === 'metric' ? 'settings-choice settings-choice--active' : 'settings-choice'}>
                  <input
                    type="radio"
                    name="measurement-units"
                    value="metric"
                    checked={units === 'metric'}
                    disabled={busy}
                    onChange={() => void changeUnits('metric')}
                  />
                  <strong>Metric</strong>
                  <span>Use metric measurements.</span>
                </label>
              </div>
            </fieldset>
          </section>

          <section className="panel settings-panel settings-span-all settings-accessibility">
            <div className="settings-accessibility-row">
              <div>
                <p className="eyebrow">ACCESSIBILITY</p>
                <strong>Text size</strong>
                <span>Browser-local display preference.</span>
              </div>
              <label className="settings-select-control">
                <span>Text size</span>
                <select
                  aria-label="Text size"
                  value={textScale}
                  onChange={(event) => changeTextScale(Number(event.target.value) as TextScalePercent)}
                >
                  {TEXT_SCALE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label} · {option.value}%
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className="settings-browser-note">You can also use browser zoom: Ctrl/Cmd + or −.</p>
          </section>

          <section className="panel settings-panel settings-span-all">
            <p className="eyebrow">PRIVACY</p>
            <h2>Your owner workspace stays private.</h2>
            <p className="muted">Garage vehicles, repair sessions, inventory, observations, and repair memory are scoped to the signed-in owner account. Administrative data-management tools are not part of the ordinary user workspace.</p>
          </section>
        </div>
      )}
    </main>
  )
}
