import { useEffect, useState, type FormEvent } from 'react'
import { ApiFailure, CSRF_HEADERS, apiRequest, formatApiFailure } from './api'
import './admin-workspace.css'

type OperatorAccess = {
  access: 'granted'
  role: 'operator_admin'
}

type ReadyHealth = {
  service: string
  status: string
  database: string
  database_ms: number
}

type ProviderKind = 'internal_data' | 'vehicle_data' | 'ai' | 'manufacturer'
type Provider = {
  id: string
  provider_key: string
  display_name: string
  provider_kind: ProviderKind
  base_url: string | null
  enabled: boolean
  capabilities: string[]
  secret_configured: boolean
  notes: string | null
  created_at: string
  updated_at: string
}

type AccessState = 'checking' | 'granted' | 'denied' | 'failed'

const PROVIDER_KINDS: Array<{ value: ProviderKind; label: string }> = [
  { value: 'internal_data', label: 'PartGraph internal data' },
  { value: 'vehicle_data', label: 'Vehicle data provider' },
  { value: 'ai', label: 'AI provider' },
  { value: 'manufacturer', label: 'Manufacturer' },
]

function kindLabel(kind: ProviderKind): string {
  return PROVIDER_KINDS.find((item) => item.value === kind)?.label ?? kind.replaceAll('_', ' ')
}

export function AdminWorkspace() {
  const [access, setAccess] = useState<AccessState>('checking')
  const [health, setHealth] = useState<ReadyHealth | null>(null)
  const [providers, setProviders] = useState<Provider[]>([])
  const [providerBusy, setProviderBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const [providerKey, setProviderKey] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [providerKind, setProviderKind] = useState<ProviderKind>('internal_data')
  const [baseUrl, setBaseUrl] = useState('')
  const [capabilities, setCapabilities] = useState('')
  const [secretRef, setSecretRef] = useState('')
  const [notes, setNotes] = useState('')
  const [enabled, setEnabled] = useState(false)

  async function loadProviders() {
    setProviders(await apiRequest<Provider[]>('/api/v1/operator/providers'))
  }

  useEffect(() => {
    let active = true
    async function load() {
      try {
        setAccess('checking')
        setError(null)
        const grant = await apiRequest<OperatorAccess>('/api/v1/operator/access')
        if (!active || grant.access !== 'granted' || grant.role !== 'operator_admin') return
        setAccess('granted')

        const [healthResult, providerResult] = await Promise.allSettled([
          apiRequest<ReadyHealth>('/api/v1/health/ready'),
          apiRequest<Provider[]>('/api/v1/operator/providers'),
        ])
        if (!active) return
        if (healthResult.status === 'fulfilled') setHealth(healthResult.value)
        if (providerResult.status === 'fulfilled') setProviders(providerResult.value)
        if (healthResult.status === 'rejected') {
          setError(formatApiFailure(healthResult.reason, 'Platform status could not be loaded.'))
        } else if (providerResult.status === 'rejected') {
          setError(formatApiFailure(providerResult.reason, 'Provider registry could not be loaded.'))
        }
      } catch (failure) {
        if (!active) return
        if (failure instanceof ApiFailure && failure.status === 403) {
          setAccess('denied')
          return
        }
        setAccess('failed')
        setError(formatApiFailure(failure, 'Administrator access could not be verified.'))
      }
    }
    void load()
    return () => { active = false }
  }, [])

  async function createProvider(event: FormEvent) {
    event.preventDefault()
    if (!providerKey.trim() || !displayName.trim()) return
    try {
      setProviderBusy(true)
      setError(null)
      setMessage(null)
      await apiRequest<Provider>('/api/v1/operator/providers', {
        method: 'POST',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider_key: providerKey.trim().toLowerCase(),
          display_name: displayName.trim(),
          provider_kind: providerKind,
          base_url: baseUrl.trim() || null,
          enabled,
          capabilities: capabilities.split(',').map((item) => item.trim()).filter(Boolean),
          secret_ref: secretRef.trim() || null,
          notes: notes.trim() || null,
        }),
      })
      setProviderKey('')
      setDisplayName('')
      setProviderKind('internal_data')
      setBaseUrl('')
      setCapabilities('')
      setSecretRef('')
      setNotes('')
      setEnabled(false)
      await loadProviders()
      setMessage('Provider configuration saved.')
    } catch (failure) {
      setError(formatApiFailure(failure, 'Provider configuration could not be saved.'))
    } finally {
      setProviderBusy(false)
    }
  }

  async function setProviderEnabled(provider: Provider, nextEnabled: boolean) {
    try {
      setProviderBusy(true)
      setError(null)
      setMessage(null)
      await apiRequest<Provider>(`/api/v1/operator/providers/${provider.id}`, {
        method: 'PATCH',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: nextEnabled }),
      })
      await loadProviders()
      setMessage(`${provider.display_name} ${nextEnabled ? 'enabled' : 'disabled'}.`)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Provider state could not be updated.'))
    } finally {
      setProviderBusy(false)
    }
  }

  if (access === 'checking') {
    return <main className="admin-shell"><section className="panel admin-access-state"><p>Verifying administrator access…</p></section></main>
  }

  if (access === 'denied') {
    return <main className="admin-shell"><section className="panel admin-access-state"><h1>Access unavailable.</h1><p>This account does not have access to operator tools.</p></section></main>
  }

  if (access === 'failed') {
    return <main className="admin-shell"><section className="panel admin-access-state"><h1>Administrator access unavailable.</h1>{error && <div className="workspace-alert workspace-alert--error">{error}</div>}</section></main>
  }

  return (
    <main className="admin-shell">
      <header className="workspace-hero admin-heading">
        <p className="eyebrow">PARTGRAPH · ADMIN</p>
        <h1>Operator workspace.</h1>
        <p>Manage PartGraph data connections here without putting provider configuration or credentials into application source.</p>
      </header>

      {error && <div className="workspace-alert workspace-alert--error">{error}</div>}
      {message && <div className="workspace-alert workspace-alert--success">{message}</div>}

      <section className="admin-status-grid" aria-label="Platform status">
        <article className="panel"><span>API</span><strong>{health?.status ?? 'Unavailable'}</strong><small>{health?.service ?? 'Status not loaded'}</small></article>
        <article className="panel"><span>Database</span><strong>{health?.database ?? 'Unavailable'}</strong><small>{health ? `${health.database_ms.toFixed(1)} ms readiness` : 'Status not loaded'}</small></article>
        <article className="panel"><span>Providers</span><strong>{providers.length}</strong><small>{providers.filter((item) => item.enabled).length} enabled</small></article>
      </section>

      <section className="admin-provider-layout">
        <div className="panel admin-provider-list">
          <div className="admin-section-heading"><div><p className="eyebrow">PROVIDERS</p><h2>Configured connections</h2></div><span>{providers.length}</span></div>
          {providers.length === 0 ? (
            <div className="admin-empty"><strong>No providers configured.</strong><p>The registry is empty until an administrator adds an internal or external data connection.</p></div>
          ) : (
            <div className="admin-provider-cards">
              {providers.map((provider) => (
                <article key={provider.id} className={provider.enabled ? 'admin-provider-card admin-provider-card--enabled' : 'admin-provider-card'}>
                  <div className="admin-provider-card__head"><div><span>{kindLabel(provider.provider_kind)}</span><strong>{provider.display_name}</strong><small>{provider.provider_key}</small></div><button type="button" disabled={providerBusy} className={provider.enabled ? 'secondary' : ''} onClick={() => void setProviderEnabled(provider, !provider.enabled)}>{provider.enabled ? 'Disable' : 'Enable'}</button></div>
                  {provider.base_url && <p>{provider.base_url}</p>}
                  <div className="admin-provider-meta"><span>{provider.secret_configured ? 'Secret reference configured' : 'No secret reference'}</span><span>{provider.capabilities.length} capabilities</span></div>
                  {provider.capabilities.length > 0 && <div className="admin-capabilities">{provider.capabilities.map((item) => <span key={item}>{item.replaceAll('_', ' ')}</span>)}</div>}
                  {provider.notes && <small className="admin-provider-notes">{provider.notes}</small>}
                </article>
              ))}
            </div>
          )}
        </div>

        <section className="panel admin-provider-form">
          <p className="eyebrow">ADD PROVIDER</p>
          <h2>Register a data connection</h2>
          <form onSubmit={(event) => void createProvider(event)}>
            <label><span>Provider key</span><input required minLength={2} maxLength={96} pattern="[a-z0-9][a-z0-9_-]{1,95}" value={providerKey} onChange={(event) => setProviderKey(event.target.value.toLowerCase().replace(/\s/g, '_'))} placeholder="provider_key" /></label>
            <label><span>Display name</span><input required maxLength={160} value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Display name" /></label>
            <label><span>Type</span><select value={providerKind} onChange={(event) => setProviderKind(event.target.value as ProviderKind)}>{PROVIDER_KINDS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
            <label><span>Base URL</span><input type="url" maxLength={1024} value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://… (optional)" /></label>
            <label><span>Capabilities</span><input value={capabilities} onChange={(event) => setCapabilities(event.target.value)} placeholder="Comma-separated capability names" /></label>
            <label><span>Server secret reference</span><input maxLength={255} value={secretRef} onChange={(event) => setSecretRef(event.target.value)} placeholder="Reference only, not the API key" /><small>PartGraph stores this reference, not the provider secret value.</small></label>
            <label><span>Notes</span><textarea rows={3} maxLength={500} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
            <label className="admin-toggle"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /><span>Enable after saving</span></label>
            <button disabled={providerBusy || !providerKey.trim() || !displayName.trim()}>{providerBusy ? 'Saving…' : 'Save provider'}</button>
          </form>
        </section>
      </section>
    </main>
  )
}
