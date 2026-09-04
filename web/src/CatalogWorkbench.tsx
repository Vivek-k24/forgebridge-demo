import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiRequest, CSRF_HEADERS, formatApiFailure } from './api'
import './catalog-workbench.css'

type JobStatus = 'queued' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'
type CollectionJob = {
  id: string
  make: string
  status: JobStatus
  cursor_position: number
  total_items: number
  processed_items: number
  collected_items: number
  verified_items: number
  last_configuration_id: string | null
  last_error: string | null
  started_at: string | null
  completed_at: string | null
  last_heartbeat_at: string | null
  created_at: string
  updated_at: string
}
type MakeProgress = {
  make: string
  candidates: number
  collected: number
  verified: number
  conflicts: number
  collection_percent: number
  verification_percent: number
  latest_job: CollectionJob | null
}
type Dashboard = {
  batch_key: string
  label: string
  verification_rule: string
  candidates: number
  collected: number
  verified: number
  conflicts: number
  collection_percent: number
  verification_percent: number
  makes: MakeProgress[]
}
type WorkbenchLog = {
  id: string
  job_id: string
  level: 'info' | 'warning' | 'error'
  event_type: string
  message: string
  details: Record<string, unknown>
  created_at: string
}
type WorkbenchSource = {
  id: string
  job_id: string
  vehicle_configuration_id: string
  provider: string
  source_url: string
  fetch_status: 'success' | 'failed' | 'blocked' | 'not_found'
  http_status: number | null
  matched_fields: Record<string, unknown>
  raw_sha256: string | null
  cache_path: string | null
  error: string | null
  fetched_at: string | null
  created_at: string
}

const BATCH_KEY = 'selected-asian-1996-2000-v1'
const POLL_MS = 2000

function percentLabel(value: number) {
  return `${value.toFixed(value % 1 === 0 ? 0 : 1)}%`
}

function ProgressBar({ value, label }: { value: number; label: string }) {
  const bounded = Math.max(0, Math.min(100, value))
  return (
    <div className="catalog-progress-row">
      <div className="catalog-progress-label"><span>{label}</span><strong>{percentLabel(bounded)}</strong></div>
      <div className="catalog-progress-track" aria-label={`${label} ${percentLabel(bounded)}`} role="progressbar" aria-valuenow={bounded} aria-valuemin={0} aria-valuemax={100}>
        <span style={{ width: `${bounded}%` }} />
      </div>
    </div>
  )
}

function jobAction(job: CollectionJob | null) {
  if (!job) return 'start'
  if (job.status === 'running' || job.status === 'queued') return 'pause'
  if (job.status === 'paused' || job.status === 'failed') return 'resume'
  return 'start'
}

function actionLabel(job: CollectionJob | null) {
  const action = jobAction(job)
  if (action === 'pause') return 'Pause'
  if (action === 'resume') return 'Resume'
  return job?.status === 'completed' ? 'Run again' : 'Start'
}

function formatTime(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

function matchedSummary(fields: Record<string, unknown>) {
  const supported = Object.entries(fields)
    .filter(([key, value]) => key !== 'staging_record_id' && key !== 'reference_model' && value === true)
    .map(([key]) => key)
  return supported.length > 0 ? supported.join(', ') : 'no configuration fields matched'
}

export function CatalogWorkbench() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [selectedMake, setSelectedMake] = useState<string>('')
  const [logs, setLogs] = useState<WorkbenchLog[]>([])
  const [sources, setSources] = useState<WorkbenchSource[]>([])
  const [busyMake, setBusyMake] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [consoleError, setConsoleError] = useState<string | null>(null)

  const selected = useMemo(
    () => dashboard?.makes.find((item) => item.make === selectedMake) ?? null,
    [dashboard, selectedMake],
  )

  const loadDashboard = useCallback(async () => {
    try {
      const data = await apiRequest<Dashboard>(`/api/v1/catalog-workbench/batches/${BATCH_KEY}`, undefined, { retryIdempotent: true })
      setDashboard(data)
      setSelectedMake((current) => current || data.makes[0]?.make || '')
      setError(null)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not load the local catalog workbench.'))
    }
  }, [])

  const loadConsole = useCallback(async (jobId: string | null) => {
    if (!jobId) {
      setLogs([])
      setSources([])
      setConsoleError(null)
      return
    }
    try {
      const [nextLogs, nextSources] = await Promise.all([
        apiRequest<WorkbenchLog[]>(`/api/v1/catalog-workbench/jobs/${jobId}/logs?limit=180`, undefined, { retryIdempotent: true }),
        apiRequest<WorkbenchSource[]>(`/api/v1/catalog-workbench/jobs/${jobId}/sources?limit=180`, undefined, { retryIdempotent: true }),
      ])
      setLogs(nextLogs)
      setSources(nextSources)
      setConsoleError(null)
    } catch (failure) {
      setConsoleError(formatApiFailure(failure, 'Could not load job logs and sources.'))
    }
  }, [])

  useEffect(() => {
    void loadDashboard()
    const timer = window.setInterval(() => void loadDashboard(), POLL_MS)
    return () => window.clearInterval(timer)
  }, [loadDashboard])

  useEffect(() => {
    const jobId = selected?.latest_job?.id ?? null
    void loadConsole(jobId)
    if (!jobId) return
    const timer = window.setInterval(() => void loadConsole(jobId), POLL_MS)
    return () => window.clearInterval(timer)
  }, [selected?.latest_job?.id, loadConsole])

  async function control(make: MakeProgress) {
    const action = jobAction(make.latest_job)
    setBusyMake(make.make)
    setError(null)
    try {
      await apiRequest(`/api/v1/catalog-workbench/batches/${BATCH_KEY}/makes/${encodeURIComponent(make.make)}/${action}`, {
        method: 'POST',
        headers: CSRF_HEADERS,
      })
      setSelectedMake(make.make)
      await loadDashboard()
    } catch (failure) {
      setError(formatApiFailure(failure, `Could not ${action} ${make.make} collection.`))
    } finally {
      setBusyMake(null)
    }
  }

  return (
    <main className="catalog-workbench">
      <header className="catalog-workbench-hero">
        <div>
          <p className="eyebrow">LOCAL DATA WORKBENCH</p>
          <h1>Catalog collection & verification</h1>
          <p>Run the research workload on this computer. Source collection, checkpoints, evidence and logs stay local until you deliberately publish verified data.</p>
        </div>
        <div className="catalog-local-badge"><i /> local worker</div>
      </header>

      {error && <div className="workspace-alert workspace-alert--error">{error}</div>}
      {!dashboard && !error && <div className="catalog-loading">Loading catalog state…</div>}

      {dashboard && (
        <>
          <section className="catalog-overall-card">
            <div className="catalog-card-heading">
              <div><p className="eyebrow">OVERALL PROGRESS</p><h2>{dashboard.label}</h2></div>
              <div className="catalog-count-stack"><strong>{dashboard.candidates}</strong><span>seed candidates</span></div>
            </div>
            <div className="catalog-overall-bars">
              <div>
                <ProgressBar value={dashboard.collection_percent} label="Collected" />
                <small>{dashboard.collected} of {dashboard.candidates} candidates completed a source pass</small>
              </div>
              <div>
                <ProgressBar value={dashboard.verification_percent} label="Verified" />
                <small>{dashboard.verified} of {dashboard.candidates} verified against a minimum of 3 independent sources · up to 5 when needed</small>
              </div>
            </div>
            {dashboard.conflicts > 0 && <div className="catalog-conflict-note">{dashboard.conflicts} configuration{dashboard.conflicts === 1 ? '' : 's'} currently require conflict review.</div>}
          </section>

          <section className="catalog-make-grid" aria-label="Collection progress by make">
            {dashboard.makes.map((make) => {
              const active = make.make === selectedMake
              const job = make.latest_job
              return (
                <article key={make.make} className={active ? 'catalog-make-card catalog-make-card--active' : 'catalog-make-card'} onClick={() => setSelectedMake(make.make)}>
                  <div className="catalog-card-heading">
                    <div><p className="eyebrow">MAKE</p><h2>{make.make}</h2></div>
                    <span className={`catalog-job-status catalog-job-status--${job?.status ?? 'idle'}`}>{job?.status ?? 'not started'}</span>
                  </div>
                  <ProgressBar value={make.collection_percent} label="Collected" />
                  <p className="catalog-card-count">{make.collected} / {make.candidates} source passes complete</p>
                  <ProgressBar value={make.verification_percent} label="Verified" />
                  <p className="catalog-card-count">{make.verified} / {make.candidates} canonical configurations verified</p>
                  {make.conflicts > 0 && <p className="catalog-card-warning">{make.conflicts} conflict{make.conflicts === 1 ? '' : 's'}</p>}
                  <div className="catalog-make-actions">
                    <button type="button" disabled={busyMake === make.make} onClick={(event) => { event.stopPropagation(); void control(make) }}>
                      {busyMake === make.make ? 'Updating…' : actionLabel(job)}
                    </button>
                    <button type="button" className="secondary" onClick={(event) => { event.stopPropagation(); setSelectedMake(make.make) }}>View activity</button>
                  </div>
                </article>
              )
            })}
          </section>

          <section className="catalog-console">
            <div className="catalog-console-header">
              <div>
                <p className="eyebrow">ACTUAL COLLECTION ACTIVITY</p>
                <h2>{selected?.make ?? 'Select a make'}</h2>
              </div>
              {selected?.latest_job && (
                <div className="catalog-console-meta">
                  <span>{selected.latest_job.status}</span>
                  <span>{selected.latest_job.processed_items}/{selected.latest_job.total_items} candidates</span>
                  <span>heartbeat {formatTime(selected.latest_job.last_heartbeat_at)}</span>
                </div>
              )}
            </div>

            {consoleError && <div className="workspace-alert workspace-alert--error">{consoleError}</div>}
            {!selected?.latest_job && <div className="catalog-empty-console">Start this make to begin collecting source evidence and producing logs.</div>}
            {selected?.latest_job?.last_error && <div className="catalog-job-error"><strong>Last worker error</strong><span>{selected.latest_job.last_error}</span></div>}

            {selected?.latest_job && (
              <div className="catalog-console-grid">
                <div className="catalog-log-pane">
                  <div className="catalog-pane-title"><strong>Worker log</strong><span>{logs.length} recent events</span></div>
                  <div className="catalog-log-list">
                    {logs.length === 0 && <p>No events yet.</p>}
                    {logs.map((entry) => (
                      <div key={entry.id} className={`catalog-log-line catalog-log-line--${entry.level}`}>
                        <time>{new Date(entry.created_at).toLocaleTimeString()}</time>
                        <span>{entry.event_type.replaceAll('_', ' ')}</span>
                        <p>{entry.message}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="catalog-source-pane">
                  <div className="catalog-pane-title"><strong>Sources</strong><span>{sources.length} recent attempts</span></div>
                  <div className="catalog-source-list">
                    {sources.length === 0 && <p>No source attempts yet.</p>}
                    {sources.map((source) => (
                      <article key={source.id} className={`catalog-source-row catalog-source-row--${source.fetch_status}`}>
                        <div className="catalog-source-row-top"><strong>{source.provider.replaceAll('_', ' ')}</strong><span>{source.fetch_status}{source.http_status ? ` · HTTP ${source.http_status}` : ''}</span></div>
                        <a href={source.source_url} target="_blank" rel="noreferrer">{source.source_url}</a>
                        <p>{matchedSummary(source.matched_fields)}</p>
                        {source.cache_path && <small>cached: {source.cache_path}</small>}
                        {source.error && <small className="catalog-source-error">{source.error}</small>}
                      </article>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  )
}