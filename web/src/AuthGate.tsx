import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { ApiFailure, CSRF_HEADERS, apiRequest } from './api'
import './auth.css'

const USERNAME_PATTERN = /^[A-Za-z0-9_]{3,32}$/

type User = {
  id: string
  email: string
  username: string
  created_at: string
}

type AuthResult = { user: User }

type AuthState =
  | { status: 'checking' }
  | { status: 'signed-out' }
  | { status: 'signed-in'; user: User }
  | { status: 'unavailable'; failure: ApiFailure }

function FailureNotice({ failure }: { failure: ApiFailure }) {
  return (
    <div className="auth-error" role="alert">
      <strong>{failure.message}</strong>
      <span>{failure.code}{failure.requestId ? ` · request ${failure.requestId}` : ''}</span>
    </div>
  )
}

export default function AuthGate({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState>({ status: 'checking' })
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [identifier, setIdentifier] = useState('')
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [failure, setFailure] = useState<ApiFailure | null>(null)

  const loadSession = useCallback(async () => {
    setAuth({ status: 'checking' })
    try {
      const result = await apiRequest<AuthResult>('/api/v1/auth/me')
      setAuth({ status: 'signed-in', user: result.user })
    } catch (error) {
      const apiFailure = error instanceof ApiFailure
        ? error
        : new ApiFailure('Could not verify session.', { code: 'CLIENT_SESSION_CHECK_FAILED' })
      if (['AUTH_REQUIRED', 'AUTH_SESSION_EXPIRED', 'AUTH_SESSION_REVOKED'].includes(apiFailure.code)) {
        setAuth({ status: 'signed-out' })
      } else {
        setAuth({ status: 'unavailable', failure: apiFailure })
      }
    }
  }, [])

  useEffect(() => {
    void loadSession()
  }, [loadSession])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFailure(null)

    if (mode === 'register' && !USERNAME_PATTERN.test(username)) {
      setFailure(new ApiFailure(
        'Username must be 3–32 characters and contain only letters, numbers, or underscore.',
        { code: 'CLIENT_USERNAME_INVALID' },
      ))
      return
    }

    setSubmitting(true)
    try {
      const result = mode === 'register'
        ? await apiRequest<AuthResult>('/api/v1/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...CSRF_HEADERS },
            body: JSON.stringify({
              email,
              username: username.toLowerCase(),
              password,
            }),
          })
        : await apiRequest<AuthResult>('/api/v1/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...CSRF_HEADERS },
            body: JSON.stringify({ identifier, password }),
          })

      setPassword('')
      setFailure(null)
      setAuth({ status: 'signed-in', user: result.user })
    } catch (error) {
      setFailure(error instanceof ApiFailure
        ? error
        : new ApiFailure('Authentication failed.', { code: 'CLIENT_AUTH_UNKNOWN_FAILURE' }))
    } finally {
      setSubmitting(false)
    }
  }

  async function logout() {
    setFailure(null)
    setSubmitting(true)
    try {
      await apiRequest<void>('/api/v1/auth/logout', {
        method: 'POST',
        headers: CSRF_HEADERS,
      })
      setAuth({ status: 'signed-out' })
      setPassword('')
    } catch (error) {
      setFailure(error instanceof ApiFailure
        ? error
        : new ApiFailure('Logout could not be confirmed.', { code: 'CLIENT_LOGOUT_UNKNOWN_FAILURE' }))
    } finally {
      setSubmitting(false)
    }
  }

  if (auth.status === 'checking') {
    return (
      <main className="auth-shell">
        <section className="auth-card auth-card--checking" aria-live="polite">
          <p className="auth-kicker">PARTGRAPH · SECURE SESSION</p>
          <div className="auth-pulse" aria-hidden="true" />
          <h1>Restoring your workspace…</h1>
          <p>Private data stays locked until the server confirms your session.</p>
        </section>
      </main>
    )
  }

  if (auth.status === 'unavailable') {
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <p className="auth-kicker">PARTGRAPH · DEGRADED</p>
          <h1>Session check unavailable.</h1>
          <FailureNotice failure={auth.failure} />
          <button type="button" onClick={() => void loadSession()}>Try again</button>
          <p className="auth-note">PartGraph does not guess that you are signed out when the network or API is unavailable.</p>
        </section>
      </main>
    )
  }

  if (auth.status === 'signed-out') {
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <div className="auth-brand">
            <p className="auth-kicker">PARTGRAPH · OWNER WORKSPACE</p>
            <h1>{mode === 'login' ? 'Sign in.' : 'Create your account.'}</h1>
            <p>One account can hold many vehicles. Session credentials stay in an HttpOnly cookie, not browser storage.</p>
          </div>

          <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
            <button type="button" className={mode === 'login' ? 'auth-tab auth-tab--active' : 'auth-tab'} onClick={() => { setMode('login'); setFailure(null) }}>Sign in</button>
            <button type="button" className={mode === 'register' ? 'auth-tab auth-tab--active' : 'auth-tab'} onClick={() => { setMode('register'); setFailure(null) }}>Create account</button>
          </div>

          <form className="auth-form" onSubmit={(event) => void submit(event)}>
            {mode === 'login' ? (
              <label>
                <span>Username or email</span>
                <input
                  required
                  value={identifier}
                  autoComplete="username"
                  maxLength={320}
                  onChange={(event) => setIdentifier(event.target.value)}
                />
              </label>
            ) : (
              <>
                <label>
                  <span>Email</span>
                  <input
                    required
                    type="email"
                    value={email}
                    autoComplete="email"
                    maxLength={320}
                    onChange={(event) => setEmail(event.target.value)}
                  />
                </label>
                <label>
                  <span>Username</span>
                  <input
                    required
                    value={username}
                    autoComplete="username"
                    minLength={3}
                    maxLength={32}
                    pattern="[A-Za-z0-9_]+"
                    title="Letters, numbers, and underscore only"
                    onChange={(event) => setUsername(event.target.value.replace(/\s/g, ''))}
                  />
                  <small>3–32 characters. Letters, numbers, and underscore only.</small>
                </label>
              </>
            )}

            <label>
              <span>Password</span>
              <input
                required
                type="password"
                value={password}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                minLength={12}
                maxLength={128}
                onChange={(event) => setPassword(event.target.value)}
              />
              {mode === 'register' && <small>Minimum 12 characters.</small>}
            </label>

            {failure && <FailureNotice failure={failure} />}
            <button className="auth-submit" type="submit" disabled={submitting}>
              {submitting ? 'Working…' : mode === 'login' ? 'Enter PartGraph' : 'Create private workspace'}
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
          <span className="account-email">@{auth.user.username} · {auth.user.email}</span>
        </div>
        {failure && <span className="account-warning">{failure.code}</span>}
        <button type="button" onClick={() => void logout()} disabled={submitting}>
          {submitting ? 'Working…' : 'Sign out'}
        </button>
      </div>
      {children}
    </div>
  )
}
