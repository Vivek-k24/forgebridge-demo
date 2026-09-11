import { useEffect, useState } from 'react'
import { ApiFailure, apiRequest, formatApiFailure } from './api'
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

type AccessState = 'checking' | 'granted' | 'denied' | 'failed'

export function AdminWorkspace() {
  const [access, setAccess] = useState<AccessState>('checking')
  const [health, setHealth] = useState<ReadyHealth | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    async function load() {
      try {
        setAccess('checking')
        setError(null)
        const grant = await apiRequest<OperatorAccess>('/api/v1/operator/access')
        if (!active || grant.access !== 'granted' || grant.role !== 'operator_admin') return
        setAccess('granted')
        try {
          setHealth(await apiRequest<ReadyHealth>('/api/v1/health/ready'))
        } catch (failure) {
          if (active) setError(formatApiFailure(failure, 'Platform status could not be loaded.'))
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
        <p>Administrative data and provider controls live outside the ordinary owner workspace.</p>
      </header>

      {error && <div className="workspace-alert workspace-alert--error">{error}</div>}

      <section className="admin-status-grid" aria-label="Platform status">
        <article className="panel">
          <span>API</span>
          <strong>{health?.status ?? 'Unavailable'}</strong>
          <small>{health?.service ?? 'Status not loaded'}</small>
        </article>
        <article className="panel">
          <span>Database</span>
          <strong>{health?.database ?? 'Unavailable'}</strong>
          <small>{health ? `${health.database_ms.toFixed(1)} ms readiness` : 'Status not loaded'}</small>
        </article>
        <article className="panel">
          <span>Access</span>
          <strong>Administrator</strong>
          <small>Server verified for this session</small>
        </article>
      </section>
    </main>
  )
}
