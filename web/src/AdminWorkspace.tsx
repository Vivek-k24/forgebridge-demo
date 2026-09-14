import { useEffect, useState, type FormEvent } from 'react'
import { ApiFailure, CSRF_HEADERS, apiRequest, formatApiFailure } from './api'
import './admin-workspace.css'

type OperatorAccess = {
  access: 'granted'
  role: 'operator_admin'
}

type PreviewOperatorBootstrapStatus = {
  available: boolean
}

type ReadyHealth = {
  service: string
  status: string
  database: string
  database_ms: number
}

type UserRole = 'owner' | 'contributor' | 'reviewer' | 'curator' | 'operator_admin'
type OperatorUser = {
  id: string
  email: string
  username: string
  role: UserRole
  is_active: boolean
  created_at: string
}

type ProviderKind = 'internal_data' | 'vehicle_data' | 'ai' | 'manufacturer'
type ProviderCredentialStorage = 'encrypted_database' | 'external_reference'
type Provider = {
  id: string
  provider_key: string
  display_name: string
  provider_kind: ProviderKind
  base_url: string | null
  enabled: boolean
  capabilities: string[]
  secret_configured: boolean
  secret_storage: ProviderCredentialStorage | null
  secret_hint: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

type SourceClass =
  | 'government'
  | 'oem_service'
  | 'licensed_oem_derived'
  | 'oem_parts'
  | 'industry_standard'
  | 'retailer'
  | 'community'
type SourceLicenseStatus = 'unreviewed' | 'approved' | 'prohibited'
type CatalogSource = {
  id: string
  source_key: string
  display_name: string
  source_class: SourceClass
  license_status: SourceLicenseStatus
  automation_allowed: boolean
  terms_url: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

type ProviderSourceBinding = {
  id: string
  provider_connection_id: string
  provider_key: string
  provider_enabled: boolean
  source_id: string
  source_key: string
  source_license_status: SourceLicenseStatus
  source_automation_allowed: boolean
  enabled: boolean
  ready_for_ingestion: boolean
  created_at: string
  updated_at: string
}

type OperatorAuditAction =
  | 'provider_created'
  | 'provider_updated'
  | 'provider_enabled'
  | 'provider_disabled'
  | 'provider_credential_saved'
  | 'provider_credential_removed'
  | 'source_created'
  | 'source_updated'
  | 'provider_source_binding_created'
  | 'provider_source_binding_enabled'
  | 'provider_source_binding_disabled'
  | 'preview_operator_bootstrap'
  | 'user_role_changed'

type OperatorAuditEvent = {
  id: string
  actor_user_id: string
  action: OperatorAuditAction
  target_type: string
  target_id: string
  event_data: Record<string, unknown>
  created_at: string
}

type AccessState = 'checking' | 'granted' | 'denied' | 'failed'

const USER_ROLES: Array<{ value: UserRole; label: string }> = [
  { value: 'owner', label: 'Owner / user' },
  { value: 'contributor', label: 'Contributor' },
  { value: 'reviewer', label: 'Reviewer' },
  { value: 'curator', label: 'Curator' },
  { value: 'operator_admin', label: 'Operator / admin' },
]

const PROVIDER_KINDS: Array<{ value: ProviderKind; label: string }> = [
  { value: 'internal_data', label: 'PartGraph internal data' },
  { value: 'vehicle_data', label: 'Vehicle data provider' },
  { value: 'ai', label: 'AI provider' },
  { value: 'manufacturer', label: 'Manufacturer' },
]

const SOURCE_CLASSES: Array<{ value: SourceClass; label: string }> = [
  { value: 'government', label: 'Government' },
  { value: 'oem_service', label: 'OEM service' },
  { value: 'licensed_oem_derived', label: 'Licensed OEM-derived' },
  { value: 'oem_parts', label: 'OEM parts' },
  { value: 'industry_standard', label: 'Industry standard' },
  { value: 'retailer', label: 'Retailer' },
  { value: 'community', label: 'Community' },
]

const SOURCE_LICENSE_STATUSES: Array<{ value: SourceLicenseStatus; label: string }> = [
  { value: 'unreviewed', label: 'Unreviewed' },
  { value: 'approved', label: 'Approved' },
  { value: 'prohibited', label: 'Prohibited' },
]

function kindLabel(kind: ProviderKind): string {
  return PROVIDER_KINDS.find((item) => item.value === kind)?.label ?? kind.replaceAll('_', ' ')
}

function sourceClassLabel(sourceClass: SourceClass): string {
  return SOURCE_CLASSES.find((item) => item.value === sourceClass)?.label ?? sourceClass.replaceAll('_', ' ')
}

function credentialLabel(provider: Provider): string {
  if (provider.secret_storage === 'encrypted_database') {
    return provider.secret_hint ? `Encrypted credential · •••• ${provider.secret_hint}` : 'Encrypted credential'
  }
  if (provider.secret_storage === 'external_reference') return 'External credential reference'
  return 'No credential configured'
}

function auditLabel(action: OperatorAuditAction): string {
  switch (action) {
    case 'provider_created': return 'Provider created'
    case 'provider_updated': return 'Provider configuration updated'
    case 'provider_enabled': return 'Provider enabled'
    case 'provider_disabled': return 'Provider disabled'
    case 'provider_credential_saved': return 'Provider credential saved'
    case 'provider_credential_removed': return 'Provider credential removed'
    case 'source_created': return 'Evidence source created'
    case 'source_updated': return 'Evidence source updated'
    case 'provider_source_binding_created': return 'Provider/source binding created'
    case 'provider_source_binding_enabled': return 'Provider/source binding enabled'
    case 'provider_source_binding_disabled': return 'Provider/source binding disabled'
    case 'preview_operator_bootstrap': return 'Preview administrator enabled'
    case 'user_role_changed': return 'User role changed'
  }
}

function auditContext(event: OperatorAuditEvent): string | null {
  const providerKey = event.event_data.provider_key
  const sourceKey = event.event_data.source_key
  if (typeof providerKey === 'string' && typeof sourceKey === 'string') return `${providerKey} → ${sourceKey}`
  if (typeof providerKey === 'string') return providerKey
  if (typeof sourceKey === 'string') return sourceKey
  const previousRole = event.event_data.previous_role
  const newRole = event.event_data.new_role
  if (typeof previousRole === 'string' && typeof newRole === 'string') {
    return `${previousRole.replaceAll('_', ' ')} → ${newRole.replaceAll('_', ' ')}`
  }
  return null
}

export function AdminWorkspace() {
  const [access, setAccess] = useState<AccessState>('checking')
  const [bootstrapAvailable, setBootstrapAvailable] = useState(false)
  const [bootstrapBusy, setBootstrapBusy] = useState(false)
  const [health, setHealth] = useState<ReadyHealth | null>(null)
  const [users, setUsers] = useState<OperatorUser[]>([])
  const [roleDrafts, setRoleDrafts] = useState<Record<string, UserRole>>({})
  const [roleBusyId, setRoleBusyId] = useState<string | null>(null)
  const [providers, setProviders] = useState<Provider[]>([])
  const [sources, setSources] = useState<CatalogSource[]>([])
  const [bindings, setBindings] = useState<ProviderSourceBinding[]>([])
  const [auditEvents, setAuditEvents] = useState<OperatorAuditEvent[]>([])
  const [providerBusy, setProviderBusy] = useState(false)
  const [sourceBusyId, setSourceBusyId] = useState<string | null>(null)
  const [bindingBusyId, setBindingBusyId] = useState<string | null>(null)
  const [credentialBusyId, setCredentialBusyId] = useState<string | null>(null)
  const [credentialDrafts, setCredentialDrafts] = useState<Record<string, string>>({})
  const [sourceLicenseDrafts, setSourceLicenseDrafts] = useState<Record<string, SourceLicenseStatus>>({})
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const [providerKey, setProviderKey] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [providerKind, setProviderKind] = useState<ProviderKind>('internal_data')
  const [baseUrl, setBaseUrl] = useState('')
  const [capabilities, setCapabilities] = useState('')
  const [credential, setCredential] = useState('')
  const [notes, setNotes] = useState('')
  const [enabled, setEnabled] = useState(false)

  const [sourceKey, setSourceKey] = useState('')
  const [sourceDisplayName, setSourceDisplayName] = useState('')
  const [sourceClass, setSourceClass] = useState<SourceClass>('government')
  const [sourceLicenseStatus, setSourceLicenseStatus] = useState<SourceLicenseStatus>('unreviewed')
  const [sourceAutomationAllowed, setSourceAutomationAllowed] = useState(false)
  const [sourceTermsUrl, setSourceTermsUrl] = useState('')
  const [sourceNotes, setSourceNotes] = useState('')

  const [bindingProviderId, setBindingProviderId] = useState('')
  const [bindingSourceId, setBindingSourceId] = useState('')

  function storeUsers(rows: OperatorUser[]) {
    setUsers(rows)
    setRoleDrafts(Object.fromEntries(rows.map((item) => [item.id, item.role])))
  }

  function storeSources(rows: CatalogSource[]) {
    setSources(rows)
    setSourceLicenseDrafts(Object.fromEntries(rows.map((item) => [item.id, item.license_status])))
  }

  async function loadOperatorData() {
    const [userRows, providerRows, sourceRows, bindingRows, auditRows] = await Promise.all([
      apiRequest<OperatorUser[]>('/api/v1/operator/users'),
      apiRequest<Provider[]>('/api/v1/operator/providers'),
      apiRequest<CatalogSource[]>('/api/v1/operator/sources'),
      apiRequest<ProviderSourceBinding[]>('/api/v1/operator/provider-source-bindings'),
      apiRequest<OperatorAuditEvent[]>('/api/v1/operator/audit'),
    ])
    storeUsers(userRows)
    setProviders(providerRows)
    storeSources(sourceRows)
    setBindings(bindingRows)
    setAuditEvents(auditRows)
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

        const [healthResult, userResult, providerResult, sourceResult, bindingResult, auditResult] = await Promise.allSettled([
          apiRequest<ReadyHealth>('/api/v1/health/ready'),
          apiRequest<OperatorUser[]>('/api/v1/operator/users'),
          apiRequest<Provider[]>('/api/v1/operator/providers'),
          apiRequest<CatalogSource[]>('/api/v1/operator/sources'),
          apiRequest<ProviderSourceBinding[]>('/api/v1/operator/provider-source-bindings'),
          apiRequest<OperatorAuditEvent[]>('/api/v1/operator/audit'),
        ])
        if (!active) return
        if (healthResult.status === 'fulfilled') setHealth(healthResult.value)
        if (userResult.status === 'fulfilled') storeUsers(userResult.value)
        if (providerResult.status === 'fulfilled') setProviders(providerResult.value)
        if (sourceResult.status === 'fulfilled') storeSources(sourceResult.value)
        if (bindingResult.status === 'fulfilled') setBindings(bindingResult.value)
        if (auditResult.status === 'fulfilled') setAuditEvents(auditResult.value)
        if (healthResult.status === 'rejected') {
          setError(formatApiFailure(healthResult.reason, 'Platform status could not be loaded.'))
        } else if (userResult.status === 'rejected') {
          setError(formatApiFailure(userResult.reason, 'User roles could not be loaded.'))
        } else if (providerResult.status === 'rejected') {
          setError(formatApiFailure(providerResult.reason, 'Provider registry could not be loaded.'))
        } else if (sourceResult.status === 'rejected') {
          setError(formatApiFailure(sourceResult.reason, 'Evidence sources could not be loaded.'))
        } else if (bindingResult.status === 'rejected') {
          setError(formatApiFailure(bindingResult.reason, 'Provider/source bindings could not be loaded.'))
        } else if (auditResult.status === 'rejected') {
          setError(formatApiFailure(auditResult.reason, 'Administrator activity could not be loaded.'))
        }
      } catch (failure) {
        if (!active) return
        if (failure instanceof ApiFailure && failure.status === 403) {
          setAccess('denied')
          try {
            const bootstrap = await apiRequest<PreviewOperatorBootstrapStatus>(
              '/api/v1/operator/preview-bootstrap/status',
            )
            if (active) setBootstrapAvailable(bootstrap.available)
          } catch {
            if (active) setBootstrapAvailable(false)
          }
          return
        }
        setAccess('failed')
        setError(formatApiFailure(failure, 'Administrator access could not be verified.'))
      }
    }
    void load()
    return () => { active = false }
  }, [])

  async function claimPreviewOperator() {
    try {
      setBootstrapBusy(true)
      setError(null)
      await apiRequest<OperatorAccess>('/api/v1/operator/preview-bootstrap', {
        method: 'POST',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
      })
      window.location.reload()
    } catch (failure) {
      setError(formatApiFailure(failure, 'Preview administrator access could not be enabled.'))
    } finally {
      setBootstrapBusy(false)
    }
  }

  async function saveUserRole(account: OperatorUser) {
    const nextRole = roleDrafts[account.id] ?? account.role
    if (nextRole === account.role) return
    try {
      setRoleBusyId(account.id)
      setError(null)
      setMessage(null)
      await apiRequest<OperatorUser>(`/api/v1/operator/users/${account.id}/role`, {
        method: 'PATCH',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: nextRole }),
      })
      await loadOperatorData()
      setMessage(`${account.username} is now ${nextRole.replaceAll('_', ' ')}.`)
    } catch (failure) {
      setRoleDrafts((current) => ({ ...current, [account.id]: account.role }))
      setError(formatApiFailure(failure, 'User role could not be changed.'))
    } finally {
      setRoleBusyId(null)
    }
  }

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
          credential: credential || null,
          notes: notes.trim() || null,
        }),
      })
      setProviderKey('')
      setDisplayName('')
      setProviderKind('internal_data')
      setBaseUrl('')
      setCapabilities('')
      setCredential('')
      setNotes('')
      setEnabled(false)
      await loadOperatorData()
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
      await loadOperatorData()
      setMessage(`${provider.display_name} ${nextEnabled ? 'enabled' : 'disabled'}.`)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Provider state could not be updated.'))
    } finally {
      setProviderBusy(false)
    }
  }

  async function saveCredential(provider: Provider) {
    const value = credentialDrafts[provider.id] ?? ''
    if (!value) return
    try {
      setCredentialBusyId(provider.id)
      setError(null)
      setMessage(null)
      await apiRequest<Provider>(`/api/v1/operator/providers/${provider.id}`, {
        method: 'PATCH',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential: value }),
      })
      setCredentialDrafts((current) => ({ ...current, [provider.id]: '' }))
      await loadOperatorData()
      setMessage(`${provider.display_name} credential encrypted and saved.`)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Provider credential could not be saved.'))
    } finally {
      setCredentialBusyId(null)
    }
  }

  async function clearCredential(provider: Provider) {
    try {
      setCredentialBusyId(provider.id)
      setError(null)
      setMessage(null)
      await apiRequest<Provider>(`/api/v1/operator/providers/${provider.id}`, {
        method: 'PATCH',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({ clear_credential: true }),
      })
      setCredentialDrafts((current) => ({ ...current, [provider.id]: '' }))
      await loadOperatorData()
      setMessage(`${provider.display_name} credential removed.`)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Provider credential could not be removed.'))
    } finally {
      setCredentialBusyId(null)
    }
  }

  async function createSource(event: FormEvent) {
    event.preventDefault()
    if (!sourceKey.trim() || !sourceDisplayName.trim()) return
    try {
      setSourceBusyId('new')
      setError(null)
      setMessage(null)
      await apiRequest<CatalogSource>('/api/v1/operator/sources', {
        method: 'POST',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_key: sourceKey.trim().toLowerCase(),
          display_name: sourceDisplayName.trim(),
          source_class: sourceClass,
          license_status: sourceLicenseStatus,
          automation_allowed: sourceAutomationAllowed,
          terms_url: sourceTermsUrl.trim() || null,
          notes: sourceNotes.trim() || null,
        }),
      })
      setSourceKey('')
      setSourceDisplayName('')
      setSourceClass('government')
      setSourceLicenseStatus('unreviewed')
      setSourceAutomationAllowed(false)
      setSourceTermsUrl('')
      setSourceNotes('')
      await loadOperatorData()
      setMessage('Evidence source saved.')
    } catch (failure) {
      setError(formatApiFailure(failure, 'Evidence source could not be saved.'))
    } finally {
      setSourceBusyId(null)
    }
  }

  async function saveSourceLicense(source: CatalogSource) {
    const nextStatus = sourceLicenseDrafts[source.id] ?? source.license_status
    if (nextStatus === source.license_status) return
    try {
      setSourceBusyId(source.id)
      setError(null)
      setMessage(null)
      await apiRequest<CatalogSource>(`/api/v1/operator/sources/${source.id}`, {
        method: 'PATCH',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          license_status: nextStatus,
          ...(nextStatus !== 'approved' && source.automation_allowed ? { automation_allowed: false } : {}),
        }),
      })
      await loadOperatorData()
      setMessage(`${source.display_name} is now ${nextStatus}.`)
    } catch (failure) {
      setSourceLicenseDrafts((current) => ({ ...current, [source.id]: source.license_status }))
      setError(formatApiFailure(failure, 'Source review state could not be updated.'))
    } finally {
      setSourceBusyId(null)
    }
  }

  async function setSourceAutomation(source: CatalogSource, nextAllowed: boolean) {
    try {
      setSourceBusyId(source.id)
      setError(null)
      setMessage(null)
      await apiRequest<CatalogSource>(`/api/v1/operator/sources/${source.id}`, {
        method: 'PATCH',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({ automation_allowed: nextAllowed }),
      })
      await loadOperatorData()
      setMessage(`${source.display_name} automated collection ${nextAllowed ? 'allowed' : 'blocked'}.`)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Source automation state could not be updated.'))
    } finally {
      setSourceBusyId(null)
    }
  }

  async function createBinding(event: FormEvent) {
    event.preventDefault()
    if (!bindingProviderId || !bindingSourceId) return
    try {
      setBindingBusyId('new')
      setError(null)
      setMessage(null)
      await apiRequest<ProviderSourceBinding>('/api/v1/operator/provider-source-bindings', {
        method: 'POST',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider_connection_id: bindingProviderId,
          source_id: bindingSourceId,
          enabled: false,
        }),
      })
      setBindingProviderId('')
      setBindingSourceId('')
      await loadOperatorData()
      setMessage('Provider/source binding created disabled. Review it before enabling.')
    } catch (failure) {
      setError(formatApiFailure(failure, 'Provider/source binding could not be created.'))
    } finally {
      setBindingBusyId(null)
    }
  }

  async function setBindingEnabled(binding: ProviderSourceBinding, nextEnabled: boolean) {
    try {
      setBindingBusyId(binding.id)
      setError(null)
      setMessage(null)
      await apiRequest<ProviderSourceBinding>(`/api/v1/operator/provider-source-bindings/${binding.id}`, {
        method: 'PATCH',
        headers: { ...CSRF_HEADERS, 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: nextEnabled }),
      })
      await loadOperatorData()
      setMessage(`Binding ${binding.provider_key} → ${binding.source_key} ${nextEnabled ? 'enabled' : 'disabled'}.`)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Provider/source binding state could not be updated.'))
    } finally {
      setBindingBusyId(null)
    }
  }

  if (access === 'checking') {
    return <main className="admin-shell"><section className="panel admin-access-state"><p>Verifying administrator access…</p></section></main>
  }

  if (access === 'denied') {
    return (
      <main className="admin-shell">
        <section className="panel admin-access-state">
          <h1>Access unavailable.</h1>
          <p>This account does not have access to operator tools.</p>
          {bootstrapAvailable && (
            <>
              <p>This isolated PartGraph preview does not have an administrator yet.</p>
              <button type="button" disabled={bootstrapBusy} onClick={() => void claimPreviewOperator()}>
                {bootstrapBusy ? 'Enabling…' : 'Enable admin for this preview'}
              </button>
            </>
          )}
          {error && <div className="workspace-alert workspace-alert--error">{error}</div>}
        </section>
      </main>
    )
  }

  if (access === 'failed') {
    return <main className="admin-shell"><section className="panel admin-access-state"><h1>Administrator access unavailable.</h1>{error && <div className="workspace-alert workspace-alert--error">{error}</div>}</section></main>
  }

  return (
    <main className="admin-shell">
      <header className="workspace-hero admin-heading">
        <p className="eyebrow">PARTGRAPH · ADMIN</p>
        <h1>Operator workspace.</h1>
        <p>Manage human access, evidence sources, and data connections without putting provider configuration or credentials into application source.</p>
      </header>

      {error && <div className="workspace-alert workspace-alert--error">{error}</div>}
      {message && <div className="workspace-alert workspace-alert--success">{message}</div>}

      <section className="admin-status-grid" aria-label="Platform status">
        <article className="panel"><span>API</span><strong>{health?.status ?? 'Unavailable'}</strong><small>{health?.service ?? 'Status not loaded'}</small></article>
        <article className="panel"><span>Database</span><strong>{health?.database ?? 'Unavailable'}</strong><small>{health ? `${health.database_ms.toFixed(1)} ms readiness` : 'Status not loaded'}</small></article>
        <article className="panel"><span>Users</span><strong>{users.length}</strong><small>{users.filter((item) => item.is_active).length} active</small></article>
        <article className="panel"><span>Providers</span><strong>{providers.length}</strong><small>{providers.filter((item) => item.enabled).length} enabled</small></article>
        <article className="panel"><span>Sources</span><strong>{sources.length}</strong><small>{sources.filter((item) => item.automation_allowed).length} automation allowed</small></article>
        <article className="panel"><span>Bindings</span><strong>{bindings.length}</strong><small>{bindings.filter((item) => item.ready_for_ingestion).length} ready</small></article>
      </section>

      <section className="panel admin-user-panel">
        <div className="admin-section-heading"><div><p className="eyebrow">HUMAN ACCESS</p><h2>Account roles</h2></div><span>{users.length}</span></div>
        <p className="admin-muted">Reviewers can verify evidence, curators are reserved for canonical publishing authority, and operator administrators manage platform access. The last active operator administrator cannot be demoted.</p>
        {users.length === 0 ? <p className="admin-muted">No accounts are available.</p> : (
          <div className="admin-user-list">
            {users.map((account) => {
              const draft = roleDrafts[account.id] ?? account.role
              const busy = roleBusyId === account.id
              return (
                <article key={account.id} className="admin-user-row">
                  <div className="admin-user-identity">
                    <strong>{account.username}</strong>
                    <span>{account.email}</span>
                    <small>{account.is_active ? 'Active account' : 'Inactive account'}</small>
                  </div>
                  <div className="admin-user-role-editor">
                    <select aria-label={`Role for ${account.username}`} value={draft} disabled={busy} onChange={(event) => setRoleDrafts((current) => ({ ...current, [account.id]: event.target.value as UserRole }))}>
                      {USER_ROLES.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}
                    </select>
                    <button type="button" disabled={busy || draft === account.role} onClick={() => void saveUserRole(account)}>{busy ? 'Saving…' : 'Save role'}</button>
                  </div>
                </article>
              )
            })}
          </div>
        )}
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
                  <div className="admin-provider-meta"><span>{credentialLabel(provider)}</span><span>{provider.capabilities.length} capabilities</span></div>
                  {provider.capabilities.length > 0 && <div className="admin-capabilities">{provider.capabilities.map((item) => <span key={item}>{item.replaceAll('_', ' ')}</span>)}</div>}
                  <div className="admin-credential-editor">
                    <label><span>{provider.secret_configured ? 'Replace credential' : 'Add credential'}</span><input type="password" autoComplete="new-password" maxLength={8192} value={credentialDrafts[provider.id] ?? ''} onChange={(event) => setCredentialDrafts((current) => ({ ...current, [provider.id]: event.target.value }))} placeholder="Paste provider access key" /></label>
                    <div className="admin-credential-actions"><button type="button" disabled={credentialBusyId === provider.id || !(credentialDrafts[provider.id] ?? '')} onClick={() => void saveCredential(provider)}>{credentialBusyId === provider.id ? 'Saving…' : provider.secret_configured ? 'Replace credential' : 'Save credential'}</button>{provider.secret_configured && <button type="button" className="secondary" disabled={credentialBusyId === provider.id} onClick={() => void clearCredential(provider)}>Remove</button>}</div>
                    <small>Saved credentials cannot be viewed again. PartGraph only shows the final four characters for identification.</small>
                  </div>
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
            <label><span>Provider access key</span><input type="password" autoComplete="new-password" minLength={4} maxLength={8192} value={credential} onChange={(event) => setCredential(event.target.value)} placeholder="Optional" /><small>Encrypted on the server before database storage. After saving, only the last four characters are shown.</small></label>
            <label><span>Notes</span><textarea rows={3} maxLength={500} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
            <label className="admin-toggle"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /><span>Enable after saving</span></label>
            <button disabled={providerBusy || !providerKey.trim() || !displayName.trim()}>{providerBusy ? 'Saving…' : 'Save provider'}</button>
          </form>
        </section>
      </section>

      <section className="admin-provider-layout">
        <div className="panel admin-provider-list">
          <div className="admin-section-heading"><div><p className="eyebrow">EVIDENCE SOURCES</p><h2>Source registry</h2></div><span>{sources.length}</span></div>
          <p className="admin-muted">Source class and source key are fixed after registration. Approval and automation are separate gates. Changing these controls does not change the source-authority matrix.</p>
          {sources.length === 0 ? <p className="admin-muted">No evidence sources registered.</p> : (
            <div className="admin-provider-cards">
              {sources.map((source) => {
                const draft = sourceLicenseDrafts[source.id] ?? source.license_status
                const busy = sourceBusyId === source.id
                return (
                  <article key={source.id} className={source.automation_allowed ? 'admin-provider-card admin-provider-card--enabled' : 'admin-provider-card'}>
                    <div className="admin-provider-card__head"><div><span>{sourceClassLabel(source.source_class)}</span><strong>{source.display_name}</strong><small>{source.source_key}</small></div><button type="button" disabled={busy || (source.license_status !== 'approved' && !source.automation_allowed)} className={source.automation_allowed ? 'secondary' : ''} onClick={() => void setSourceAutomation(source, !source.automation_allowed)}>{source.automation_allowed ? 'Block automation' : 'Allow automation'}</button></div>
                    <div className="admin-provider-meta"><span>License: {source.license_status}</span><span>{source.automation_allowed ? 'Automation allowed' : 'Automation blocked'}</span></div>
                    <div className="admin-user-role-editor">
                      <select aria-label={`License status for ${source.display_name}`} value={draft} disabled={busy} onChange={(event) => setSourceLicenseDrafts((current) => ({ ...current, [source.id]: event.target.value as SourceLicenseStatus }))}>
                        {SOURCE_LICENSE_STATUSES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                      </select>
                      <button type="button" disabled={busy || draft === source.license_status} onClick={() => void saveSourceLicense(source)}>{busy ? 'Saving…' : 'Save review state'}</button>
                    </div>
                    {source.terms_url && <p>{source.terms_url}</p>}
                    {source.notes && <small className="admin-provider-notes">{source.notes}</small>}
                  </article>
                )
              })}
            </div>
          )}
        </div>

        <section className="panel admin-provider-form">
          <p className="eyebrow">ADD SOURCE</p>
          <h2>Register evidence origin</h2>
          <form onSubmit={(event) => void createSource(event)}>
            <label><span>Source key</span><input required maxLength={128} pattern="[a-z0-9][a-z0-9_.-]{0,127}" value={sourceKey} onChange={(event) => setSourceKey(event.target.value.toLowerCase().replace(/\s/g, '-'))} placeholder="nhtsa-recalls" /></label>
            <label><span>Display name</span><input required maxLength={180} value={sourceDisplayName} onChange={(event) => setSourceDisplayName(event.target.value)} placeholder="Evidence source" /></label>
            <label><span>Source class</span><select value={sourceClass} onChange={(event) => setSourceClass(event.target.value as SourceClass)}>{SOURCE_CLASSES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><small>Source class is immutable after registration because it affects trust policy.</small></label>
            <label><span>License review</span><select value={sourceLicenseStatus} onChange={(event) => { const value = event.target.value as SourceLicenseStatus; setSourceLicenseStatus(value); if (value !== 'approved') setSourceAutomationAllowed(false) }}>{SOURCE_LICENSE_STATUSES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
            <label><span>Terms URL</span><input type="url" maxLength={1024} value={sourceTermsUrl} onChange={(event) => setSourceTermsUrl(event.target.value)} placeholder="https://… (optional)" /></label>
            <label><span>Notes</span><textarea rows={3} maxLength={1000} value={sourceNotes} onChange={(event) => setSourceNotes(event.target.value)} /></label>
            <label className="admin-toggle"><input type="checkbox" disabled={sourceLicenseStatus !== 'approved'} checked={sourceAutomationAllowed} onChange={(event) => setSourceAutomationAllowed(event.target.checked)} /><span>Allow automated collection</span></label>
            <button disabled={sourceBusyId === 'new' || !sourceKey.trim() || !sourceDisplayName.trim()}>{sourceBusyId === 'new' ? 'Saving…' : 'Save source'}</button>
          </form>
        </section>
      </section>

      <section className="admin-provider-layout">
        <div className="panel admin-provider-list">
          <div className="admin-section-heading"><div><p className="eyebrow">PROVIDER → SOURCE</p><h2>Trusted bindings</h2></div><span>{bindings.length}</span></div>
          <p className="admin-muted">A binding identifies which registered evidence source a provider is allowed to represent. Creating a binding never starts collection; every new binding starts disabled.</p>
          {bindings.length === 0 ? <p className="admin-muted">No provider/source bindings registered.</p> : (
            <div className="admin-provider-cards">
              {bindings.map((binding) => {
                const busy = bindingBusyId === binding.id
                const canEnable = binding.provider_enabled && binding.source_license_status === 'approved' && binding.source_automation_allowed
                return (
                  <article key={binding.id} className={binding.ready_for_ingestion ? 'admin-provider-card admin-provider-card--enabled' : 'admin-provider-card'}>
                    <div className="admin-provider-card__head"><div><span>{binding.ready_for_ingestion ? 'Ready' : binding.enabled ? 'Blocked by dependency' : 'Disabled'}</span><strong>{binding.provider_key} → {binding.source_key}</strong><small>{binding.source_license_status} source · provider {binding.provider_enabled ? 'enabled' : 'disabled'}</small></div><button type="button" className={binding.enabled ? 'secondary' : ''} disabled={busy || (!binding.enabled && !canEnable)} onClick={() => void setBindingEnabled(binding, !binding.enabled)}>{binding.enabled ? 'Disable binding' : 'Enable binding'}</button></div>
                    <div className="admin-provider-meta"><span>{binding.source_automation_allowed ? 'Source automation allowed' : 'Source automation blocked'}</span><span>{binding.ready_for_ingestion ? 'All configuration gates satisfied' : 'No collection authority'}</span></div>
                  </article>
                )
              })}
            </div>
          )}
        </div>

        <section className="panel admin-provider-form">
          <p className="eyebrow">ADD BINDING</p>
          <h2>Connect provider to source</h2>
          <form onSubmit={(event) => void createBinding(event)}>
            <label><span>Provider</span><select required value={bindingProviderId} onChange={(event) => setBindingProviderId(event.target.value)}><option value="">Choose provider</option>{providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.display_name} · {provider.enabled ? 'enabled' : 'disabled'}</option>)}</select></label>
            <label><span>Evidence source</span><select required value={bindingSourceId} onChange={(event) => setBindingSourceId(event.target.value)}><option value="">Choose source</option>{sources.map((source) => <option key={source.id} value={source.id}>{source.display_name} · {source.license_status}{source.automation_allowed ? ' · automation allowed' : ''}</option>)}</select></label>
            <p className="admin-muted">The pair is immutable after creation. The new binding will be disabled until you explicitly enable it.</p>
            <button disabled={bindingBusyId === 'new' || !bindingProviderId || !bindingSourceId}>{bindingBusyId === 'new' ? 'Saving…' : 'Create disabled binding'}</button>
          </form>
        </section>
      </section>

      <section className="panel admin-audit-panel">
        <div className="admin-section-heading"><div><p className="eyebrow">ADMIN ACTIVITY</p><h2>Recent changes</h2></div><span>{auditEvents.length}</span></div>
        {auditEvents.length === 0 ? <p className="admin-muted">No administrator changes recorded yet.</p> : (
          <ol className="admin-audit-list">
            {auditEvents.map((event) => (
              <li key={event.id}>
                <div><strong>{auditLabel(event.action)}</strong>{auditContext(event) && <span>{auditContext(event)}</span>}</div>
                <time dateTime={event.created_at}>{new Date(event.created_at).toLocaleString()}</time>
              </li>
            ))}
          </ol>
        )}
      </section>
    </main>
  )
}