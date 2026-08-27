import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import './auth.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const CSRF_HEADERS = { 'Content-Type': 'application/json', 'X-PartGraph-CSRF': '1' }

type User = {
  id: string
  email: string
  created_at: string
}

type AuthPayload = { user: User }

type AuthState =
  | { status: 'checking' }
  | { status: 'guest' }
  | { status: 'ready'; user: User }

async function authRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: 'include',
  })
  if (!response.ok) {
    let message = response.status === 401 ? 'Email or password was not accepted.' : `Request failed (${response.status}).`
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) message = payload.detail
    } catch {
      // Keep the status-based fallback.
    }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export default function AuthGate({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState>({ status: 'checking' })
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [working, setWorking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void authRequest<AuthPayload>('/api/v1/auth/me')
      .then((payload) => setAuth({ status: 'ready', user: payload.user }))
      .catch(() => setAuth({ status: 'guest' }))
  }, [])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setWorking(true)
    setError(null)
    try {
      const payload = await authRequest<AuthPayload>(
        mode === 'login' ? '/api/v1/auth/login' : '/api/v1/auth/register',
        {
          method: 'POST',
          headers: CSRF_HEADERS,
          body: JSON.stringify({ email, password }),
        },
      )
      setPassword('')
      setAuth({ status: 'ready', user: payload.user })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Authentication failed.')
    } finally {
      setWorking(false)
    }
  }

  async function logout() {
    setWorking(true)
    try {
      await authRequest<void>('/api/v1/auth/logout', {
        method: 'POST',
        headers: { 'X-PartGraph-CSRF': '1' },
      })
    } finally {
      setEmail('')
      setPassword('')
      setAuth({ status: 'guest' })
      setWorking(false)
    }
  }

  if (auth.status === 'checking') {
    return (
      <main className="auth-shell">
        <section className="auth-card auth-card--checking">
          <p className="auth-kicker">PARTGRAPH · SECURE SESSION</p>
          <div className="auth-pulse" aria-hidden="true" />
          <h1>Restoring your workspace…</h1>
        </section>
      </main>
    )
  }

  if (auth.status === 'guest') {
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <div className="auth-brand">
            <p className="auth-kicker">PARTGRAPH · OWNER WORKSPACE</p>
            <h1>Your repair state starts with a private account.</h1>
            <p>
              One account can hold many vehicles. VINs, photos, repair sessions, inventory, and
              fastener state stay behind this user boundary.
            </p>
          </div>

          <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
            <button
              type="button"
              className={mode === 'login' ? 'auth-tab auth-tab--active' : 'auth-tab'}
              onClick={() => { setMode('login'); setError(null) }}
            >
              Sign in
            </button>
            <button
              type="button"
              className={mode === 'register' ? 'auth-tab auth-tab--active' : 'auth-tab'}
              onClick={() => { setMode('register'); setError(null) }}
            >
              Create account
            </button>
          </div>

          <form className="auth-form" onSubmit={submit}>
            <label>
              <span>Email</span>
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                required
              />
            </label>
            <label>
              <span>Password</span>
              <input
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                value={password}
                minLength={12}
                maxLength={128}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={mode === 'register' ? '12+ characters' : 'Your password'}
                required
              />
            </label>
            {error && <p className="auth-error" role="alert">{error}</p>}
            <button className="auth-submit" type="submit" disabled={working}>
              {working ? 'Working…' : mode === 'login' ? 'Enter PartGraph' : 'Create private workspace'}
            </button>
          </form>

          <div className="auth-security-grid">
            <span>ARGON2ID PASSWORD HASH</span>
            <span>HTTPONLY SESSION</span>
            <span>POSTGRESQL RLS</span>
          </div>
        </section>
      </main>
    )
  }

  return (
    <div className="authenticated-shell">
      <div className="account-strip">
        <div>
          <span className="account-dot" aria-hidden="true" />
          <span className="account-status">PRIVATE SESSION</span>
          <span className="account-email">{auth.user.email}</span>
        </div>
        <button type="button" onClick={() => void logout()} disabled={working}>Sign out</button>
      </div>
      {children}
    </div>
  )
}
