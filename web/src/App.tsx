import { useCallback, useEffect, useState } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const HARD_TIMEOUT_MS = 10_000

type RuntimeState =
  | { status: 'checking' }
  | { status: 'ready'; requestMs: number; databaseMs: number }
  | { status: 'unavailable'; message: string }

function App() {
  const [runtime, setRuntime] = useState<RuntimeState>({ status: 'checking' })

  const checkRuntime = useCallback(async () => {
    setRuntime({ status: 'checking' })
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), HARD_TIMEOUT_MS)
    const started = performance.now()

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/health/ready`, {
        signal: controller.signal,
      })
      if (!response.ok) throw new Error(`API returned ${response.status}`)

      const payload = (await response.json()) as { database_ms: number }
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
    } finally {
      window.clearTimeout(timeout)
    }
  }, [])

  useEffect(() => {
    void checkRuntime()
  }, [checkRuntime])

  return (
    <main className="shell">
      <section className="panel">
        <p className="eyebrow">PARTGRAPH · BLOCK 1</p>
        <h1>Runtime foundation</h1>
        <p className="lede">
          The interactive path is isolated from catalog collection: web → API modular monolith → PostgreSQL.
        </p>

        <div className="status" aria-live="polite">
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
        </div>

        <div className="rules">
          <div><span>Target</span><strong>p95 &lt; 3 s</strong></div>
          <div><span>Hard block</span><strong>10 s</strong></div>
          <div><span>Collector</span><strong>off user path</strong></div>
        </div>

        <button type="button" onClick={() => void checkRuntime()} disabled={runtime.status === 'checking'}>
          Check again
        </button>
      </section>
    </main>
  )
}

export default App
