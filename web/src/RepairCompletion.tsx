import { useCallback, useEffect, useMemo, useState } from 'react'
import { activeRepairSessionId, preferredRepairSessionId, setActiveRepairSessionId } from './active-repair'
import { ApiFailure, apiRequest, CSRF_HEADERS, formatApiFailure } from './api'
import { partGraphDeviceId } from './device'

type RepairSession = { id: string; title: string }
type Lease = { status: 'available' | 'owned' | 'held_by_other'; can_edit: boolean }
type ResumeSnapshot = { session: RepairSession; lease: Lease }
type CompletionStatus =
  | 'not_started'
  | 'active'
  | 'blocked'
  | 'physical_replacement_performed'
  | 'supported_work_complete'
  | 'downstream_required_pending'
  | 'unsupported_or_professional_pending'
  | 'fully_mechanically_complete'
  | 'archived'

type DownstreamRequirement = {
  requirement_id: string
  title: string
  detail: string | null
  support_state: 'supported' | 'professional_required' | 'unsupported'
  target_repair_title: string | null
  state: 'pending' | 'satisfied'
  resolution_kind: 'linked_session_complete' | 'external_service_confirmed' | null
  resolution_session_id: string | null
}

type Completion = {
  session_id: string
  repair_title: string
  completion_status: CompletionStatus
  physical_replacement_expected: boolean
  physical_replacement_performed: boolean
  supported_partgraph_work_complete: boolean
  fully_mechanically_complete: boolean
  downstream_total: number
  downstream_pending: number
  downstream_satisfied: number
  unsupported_action_titles: string[]
  downstream_requirements: DownstreamRequirement[]
}

const RECOVERY_DELAYS_MS = [0, 350, 1_000]

function statusLabel(status: CompletionStatus): string {
  if (status === 'not_started') return 'Repair work has not started'
  if (status === 'active') return 'Repair is in progress'
  if (status === 'blocked') return 'Repair is blocked'
  if (status === 'physical_replacement_performed') return 'Replacement performed · more work remains'
  if (status === 'supported_work_complete') return 'PartGraph-supported work is complete'
  if (status === 'downstream_required_pending') return 'Required follow-up work remains'
  if (status === 'unsupported_or_professional_pending') return 'Required outside service remains'
  if (status === 'fully_mechanically_complete') return 'Repair is mechanically complete'
  return 'Repair session is archived'
}

function supportLabel(state: DownstreamRequirement['support_state']): string {
  if (state === 'supported') return 'Supported in PartGraph'
  if (state === 'professional_required') return 'Professional service required'
  return 'Outside PartGraph support'
}

function ambiguousTransportFailure(error: unknown): error is ApiFailure {
  return error instanceof ApiFailure
    && (error.code === 'CLIENT_REQUEST_TIMEOUT' || error.code === 'CLIENT_NETWORK_FAILURE')
}

function uncertainCompletionWrite(error: ApiFailure): ApiFailure {
  return new ApiFailure(
    'PartGraph could not confirm whether the completion change committed. Reload completion before trying again.',
    {
      code: 'CLIENT_WRITE_STATE_UNCERTAIN',
      requestId: error.requestId,
      retryable: false,
      status: error.status,
    },
  )
}

async function wait(milliseconds: number): Promise<void> {
  if (milliseconds <= 0) return
  await new Promise((resolve) => window.setTimeout(resolve, milliseconds))
}

async function recoverCompletion(
  sessionId: string,
  committed: (value: Completion) => boolean,
): Promise<Completion | null> {
  for (const delay of RECOVERY_DELAYS_MS) {
    await wait(delay)
    try {
      const value = await apiRequest<Completion>(
        `/api/v1/repair-sessions/${sessionId}/completion`,
        {},
        { retryIdempotent: true },
      )
      if (committed(value)) return value
    } catch {
      // Recovery is best-effort. If it cannot establish the result, surface uncertainty.
    }
  }
  return null
}

export function RepairCompletionWorkspace() {
  const deviceId = useMemo(() => partGraphDeviceId(), [])
  const [sessions, setSessions] = useState<RepairSession[]>([])
  const [selectedId, setSelectedId] = useState(() => activeRepairSessionId() || '')
  const [lease, setLease] = useState<Lease | null>(null)
  const [completion, setCompletion] = useState<Completion | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const loadSession = useCallback(async (sessionId: string) => {
    setCompletion(null)
    setLease(null)
    setError(null)
    if (!sessionId) {
      setActiveRepairSessionId(null)
      return
    }
    const [resume, result] = await Promise.all([
      apiRequest<ResumeSnapshot>(
        `/api/v1/repair-sessions/${sessionId}/resume`,
        { headers: { 'X-PartGraph-Device-ID': deviceId } },
        { retryIdempotent: true },
      ),
      apiRequest<Completion>(
        `/api/v1/repair-sessions/${sessionId}/completion`,
        {},
        { retryIdempotent: true },
      ),
    ])
    setActiveRepairSessionId(sessionId)
    setLease(resume.lease)
    setCompletion(result)
  }, [deviceId])

  const refresh = useCallback(async (preferredId?: string) => {
    const rows = await apiRequest<RepairSession[]>('/api/v1/repair-sessions', {}, { retryIdempotent: true })
    setSessions(rows)
    const nextId = preferredRepairSessionId(rows, preferredId)
    setSelectedId(nextId)
    await loadSession(nextId)
  }, [loadSession])

  useEffect(() => {
    let active = true
    async function initialize() {
      try {
        setLoading(true)
        await refresh(activeRepairSessionId() || undefined)
      } catch (failure) {
        if (active) setError(formatApiFailure(failure, 'Could not load repair completion.'))
      } finally {
        if (active) setLoading(false)
      }
    }
    void initialize()
    return () => { active = false }
  }, [refresh])

  async function chooseSession(sessionId: string) {
    setSelectedId(sessionId)
    setMessage(null)
    try {
      setLoading(true)
      await loadSession(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not load repair completion.'))
    } finally {
      setLoading(false)
    }
  }

  async function leaseAction(takeover: boolean) {
    if (!selectedId) return
    try {
      setBusy(true)
      setError(null)
      await apiRequest(
        `/api/v1/repair-sessions/${selectedId}/lease/${takeover ? 'takeover' : 'acquire'}`,
        {
          method: 'POST',
          headers: { ...CSRF_HEADERS, 'X-PartGraph-Device-ID': deviceId },
        },
      )
      await loadSession(selectedId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not take editing control.'))
    } finally {
      setBusy(false)
    }
  }

  async function startLinkedRepair(item: DownstreamRequirement) {
    if (!selectedId) return
    try {
      setBusy(true)
      setError(null)
      try {
        const result = await apiRequest<Completion>(
          `/api/v1/repair-sessions/${selectedId}/completion/downstream/${item.requirement_id}/start`,
          {
            method: 'POST',
            headers: { ...CSRF_HEADERS, 'X-PartGraph-Device-ID': deviceId },
          },
        )
        setCompletion(result)
      } catch (failure) {
        if (!ambiguousTransportFailure(failure)) throw failure
        const recovered = await recoverCompletion(selectedId, (value) => {
          const target = value.downstream_requirements.find(
            (requirement) => requirement.requirement_id === item.requirement_id,
          )
          return target?.state === 'satisfied' || target?.resolution_session_id !== null
        })
        if (!recovered) throw uncertainCompletionWrite(failure)
        setCompletion(recovered)
      }
      setMessage('Required PartGraph repair started and linked to this repair.')
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not start the required repair.'))
    } finally {
      setBusy(false)
    }
  }

  async function resolve(item: DownstreamRequirement) {
    if (!selectedId) return
    const linked = item.support_state === 'supported'
    const resolutionKind = linked ? 'linked_session_complete' : 'external_service_confirmed'
    try {
      setBusy(true)
      setError(null)
      try {
        const result = await apiRequest<Completion>(
          `/api/v1/repair-sessions/${selectedId}/completion/downstream/${item.requirement_id}`,
          {
            method: 'PUT',
            headers: {
              ...CSRF_HEADERS,
              'Content-Type': 'application/json',
              'X-PartGraph-Device-ID': deviceId,
            },
            body: JSON.stringify({ resolution_kind: resolutionKind }),
          },
        )
        setCompletion(result)
      } catch (failure) {
        if (!ambiguousTransportFailure(failure)) throw failure
        const recovered = await recoverCompletion(selectedId, (value) => {
          const target = value.downstream_requirements.find(
            (requirement) => requirement.requirement_id === item.requirement_id,
          )
          return target?.state === 'satisfied' && target.resolution_kind === resolutionKind
        })
        if (!recovered) throw uncertainCompletionWrite(failure)
        setCompletion(recovered)
      }
      setMessage(linked ? 'Linked repair verified complete.' : 'External completion recorded.')
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not resolve this required follow-up.'))
    } finally {
      setBusy(false)
    }
  }

  function openLinkedRepair(sessionId: string) {
    setActiveRepairSessionId(sessionId)
    window.location.hash = '#/guidance'
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  if (loading && sessions.length === 0) {
    return <section className="guided-workspace panel"><p>Loading repair completion…</p></section>
  }

  return (
    <section className="guided-workspace panel" aria-label="Repair completion">
      <header className="guided-heading">
        <div>
          <p className="eyebrow">PARTGRAPH · COMPLETION</p>
          <h1>Replacing the part does not always finish the repair.</h1>
          <p className="lede">PartGraph keeps replacement, supported work, follow-up work, and final mechanical completion separate.</p>
        </div>
        {sessions.length > 0 && (
          <label className="guided-session-picker">
            <span>Repair session</span>
            <select value={selectedId} disabled={busy} onChange={(event) => void chooseSession(event.target.value)}>
              {sessions.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
            </select>
          </label>
        )}
      </header>

      {error && <div className="repair-alert repair-alert--error">{error}</div>}
      {message && <div className="repair-alert repair-alert--success">{message}</div>}

      {sessions.length === 0 ? (
        <div className="guided-boundary guided-boundary--neutral"><strong>No repair session is open.</strong></div>
      ) : completion ? (
        <>
          <div className="guided-complete">
            <span aria-hidden="true">{completion.fully_mechanically_complete ? '✓' : '•'}</span>
            <div><strong>{statusLabel(completion.completion_status)}</strong><p>{completion.repair_title}</p></div>
          </div>

          <div className="guided-meta">
            <div>
              <span>Physical replacement</span>
              <strong>{!completion.physical_replacement_expected ? 'Not part of this repair definition' : completion.physical_replacement_performed ? 'Performed' : 'Not yet recorded'}</strong>
            </div>
            <div><span>PartGraph-supported work</span><strong>{completion.supported_partgraph_work_complete ? 'Complete' : 'In progress'}</strong></div>
            <div><span>Required follow-up</span><strong>{completion.downstream_pending > 0 ? `${completion.downstream_pending} pending` : 'No pending follow-up'}</strong></div>
          </div>

          {completion.unsupported_action_titles.length > 0 && (
            <div className="guided-boundary guided-boundary--professional">
              <strong>Required work remains outside PartGraph guidance.</strong>
              <ul>{completion.unsupported_action_titles.map((title) => <li key={title}>{title}</li>)}</ul>
            </div>
          )}

          <section className="guided-plan">
            <div className="guided-plan-head">
              <div><p className="eyebrow">REQUIRED FOLLOW-UP</p><h3>Downstream work</h3></div>
              <span>{completion.downstream_satisfied} of {completion.downstream_total} resolved</span>
            </div>
            {completion.downstream_requirements.length === 0 ? (
              <div className="guided-boundary guided-boundary--neutral">
                <strong>No downstream requirement has been activated.</strong>
                <p>If verified repair data triggers additional required work, it will appear here automatically.</p>
              </div>
            ) : (
              <ol>
                {completion.downstream_requirements.map((item, index) => (
                  <li key={item.requirement_id} className={`guided-plan-item guided-plan-item--${item.state === 'satisfied' ? 'completed' : 'pending'}`}>
                    <span>{index + 1}</span>
                    <div>
                      <strong>{item.title}</strong>
                      <small>{supportLabel(item.support_state)} · {item.state === 'satisfied' ? 'Resolved' : 'Required'}</small>
                      {item.detail && <p>{item.detail}</p>}
                      {item.target_repair_title && <p>Related PartGraph repair: <strong>{item.target_repair_title}</strong></p>}
                      {item.state === 'pending' && item.support_state === 'supported' && item.resolution_session_id === null && (
                        <div className="guided-action-buttons">
                          <button type="button" disabled={busy || !lease?.can_edit} onClick={() => void startLinkedRepair(item)}>Start required repair</button>
                        </div>
                      )}
                      {item.state === 'pending' && item.support_state === 'supported' && item.resolution_session_id !== null && (
                        <div className="guided-action-buttons">
                          <button type="button" disabled={busy} onClick={() => openLinkedRepair(item.resolution_session_id as string)}>Open required repair</button>
                          <button type="button" disabled={busy || !lease?.can_edit} onClick={() => void resolve(item)}>Verify linked repair complete</button>
                        </div>
                      )}
                      {item.state === 'pending' && item.support_state !== 'supported' && (
                        <div className="guided-action-buttons">
                          <button type="button" disabled={busy || !lease?.can_edit} onClick={() => void resolve(item)}>Confirm external service complete</button>
                        </div>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <div className="guided-controls">
            {lease?.status === 'available' && <button type="button" disabled={busy} onClick={() => void leaseAction(false)}>Take editing control</button>}
            {lease?.status === 'held_by_other' && <button type="button" disabled={busy} onClick={() => void leaseAction(true)}>Take over session</button>}
            <span>{lease?.can_edit ? 'Completion updates are available on this device.' : 'View only until editing control is available.'}</span>
          </div>
        </>
      ) : null}
    </section>
  )
}
