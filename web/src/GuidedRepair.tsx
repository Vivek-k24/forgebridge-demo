import { useCallback, useEffect, useMemo, useState } from 'react'
import { activeRepairSessionId, preferredRepairSessionId, setActiveRepairSessionId } from './active-repair'
import { AssistanceExplanation } from './AssistanceExplanation'
import { ApiFailure, apiRequest, CSRF_HEADERS, formatApiFailure } from './api'
import { newIdempotencyKey, partGraphDeviceId } from './device'
import './guided-repair.css'

type SessionStatus = 'active' | 'paused' | 'archived'
type LeaseStatus = 'available' | 'owned' | 'held_by_other'
type ProgressState = 'pending' | 'completed' | 'skipped' | 'blocked'
type GuidanceStatus = 'action_available' | 'action_blocked' | 'inventory_blocked' | 'procedure_complete'

type RepairSession = {
  id: string
  user_vehicle_id: string
  title: string
  status: SessionStatus
  current_sequence: number
  archived_at: string | null
  created_at: string
  updated_at: string
}

type Lease = {
  status: LeaseStatus
  can_edit: boolean
  expires_at: string | null
}

type ResumeSnapshot = {
  session: RepairSession
  lease: Lease
}

type InventoryBlocker = {
  requirement_definition_id: string
  requirement_key: string
  display_name: string
  readiness_state: string
  quantity_available: string
  required_quantity: string | null
  unit: string | null
}

type GuidanceAction = {
  action_id: string
  action_key: string
  title: string
  instruction: string
  warning_text: string | null
  workspace_note: string | null
  position: number
  skippable: boolean
  progress_state: ProgressState
  blocker_code: string | null
  notes: string | null
  dependency_action_keys: string[]
  inventory_blockers: InventoryBlocker[]
  supporting_claim_ids: string[]
}

type GuidanceSummary = {
  total: number
  completed: number
  skipped: number
  blocked: number
  pending: number
}

type Guidance = {
  session_id: string
  repair_definition_id: string
  repair_key: string
  repair_title: string
  version: number
  definition_status: string
  capability_policy_key: string
  status: GuidanceStatus
  procedure_complete: boolean
  current_action: GuidanceAction | null
  summary: GuidanceSummary
}

type GuidancePlan = Guidance & {
  actions: GuidanceAction[]
}

type Boundary = {
  code: string
  title: string
  detail: string
  severity: 'neutral' | 'professional' | 'prohibited'
}

const EXPECTED_BOUNDARIES: Record<string, Omit<Boundary, 'code' | 'detail'>> = {
  REPAIR_PROCEDURE_NOT_AVAILABLE: {
    title: 'Verified guidance is not available for this session yet.',
    severity: 'neutral',
  },
  REPAIR_GUIDANCE_PROFESSIONAL_REQUIRED: {
    title: 'This repair requires professional service.',
    severity: 'professional',
  },
  REPAIR_GUIDANCE_PROHIBITED: {
    title: 'Guided repair is blocked by PartGraph safety policy.',
    severity: 'prohibited',
  },
}

function requestHeaders(deviceId: string, idempotencyKey?: string): Record<string, string> {
  return {
    ...CSRF_HEADERS,
    'X-PartGraph-Device-ID': deviceId,
    ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}),
  }
}

function human(value: string): string {
  return value.replaceAll('_', ' ').replaceAll('-', ' ')
}

function quantityLabel(blocker: InventoryBlocker): string {
  if (!blocker.required_quantity) return human(blocker.readiness_state)
  const unit = blocker.unit ? ` ${blocker.unit}` : ''
  return `${human(blocker.readiness_state)} · need ${blocker.required_quantity}${unit}`
}

export function GuidedRepairWorkspace({
  onOpenReadiness,
  onStartRepair,
}: {
  onOpenReadiness: () => void
  onStartRepair: () => void
}) {
  const deviceId = useMemo(() => partGraphDeviceId(), [])
  const [sessions, setSessions] = useState<RepairSession[]>([])
  const [selectedId, setSelectedId] = useState(() => activeRepairSessionId() || '')
  const [lease, setLease] = useState<Lease | null>(null)
  const [guidance, setGuidance] = useState<Guidance | null>(null)
  const [plan, setPlan] = useState<GuidancePlan | null>(null)
  const [boundary, setBoundary] = useState<Boundary | null>(null)
  const [showPlan, setShowPlan] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadSession = useCallback(async (sessionId: string) => {
    setError(null)
    setBoundary(null)
    setGuidance(null)
    setPlan(null)
    setShowPlan(false)

    if (!sessionId) {
      setLease(null)
      setActiveRepairSessionId(null)
      return
    }

    const resume = await apiRequest<ResumeSnapshot>(
      `/api/v1/repair-sessions/${sessionId}/resume`,
      { headers: { 'X-PartGraph-Device-ID': deviceId } },
      { retryIdempotent: true },
    )
    setLease(resume.lease)
    setActiveRepairSessionId(sessionId)

    try {
      const current = await apiRequest<Guidance>(
        `/api/v1/repair-sessions/${sessionId}/guidance`,
        {},
        { retryIdempotent: true },
      )
      setGuidance(current)
    } catch (failure) {
      if (failure instanceof ApiFailure && EXPECTED_BOUNDARIES[failure.code]) {
        const definition = EXPECTED_BOUNDARIES[failure.code]
        setBoundary({
          code: failure.code,
          title: definition.title,
          detail: failure.message,
          severity: definition.severity,
        })
        return
      }
      throw failure
    }
  }, [deviceId])

  const refresh = useCallback(async (preferredId?: string) => {
    const rows = await apiRequest<RepairSession[]>(
      '/api/v1/repair-sessions',
      {},
      { retryIdempotent: true },
    )
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
        if (active) setError(formatApiFailure(failure, 'Could not load guided repair.'))
      } finally {
        if (active) setLoading(false)
      }
    }
    void initialize()
    return () => {
      active = false
    }
  }, [refresh])

  async function chooseSession(sessionId: string) {
    setSelectedId(sessionId)
    setActiveRepairSessionId(sessionId)
    setMessage(null)
    try {
      setLoading(true)
      await loadSession(sessionId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not open guided repair.'))
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
        { method: 'POST', headers: requestHeaders(deviceId) },
      )
      setMessage(takeover ? 'Editing control moved to this device.' : 'Editing control acquired.')
      await loadSession(selectedId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not acquire editing control.'))
    } finally {
      setBusy(false)
    }
  }

  async function updateProgress(progressState: 'completed' | 'skipped' | 'blocked') {
    const action = guidance?.current_action
    if (!selectedId || !action) return
    try {
      setBusy(true)
      setError(null)
      setMessage(null)
      const payload = progressState === 'blocked'
        ? { progress_state: progressState, blocker_code: 'owner_reported_problem' }
        : { progress_state: progressState }
      await apiRequest<Guidance>(
        `/api/v1/repair-sessions/${selectedId}/guidance/actions/${action.action_id}`,
        {
          method: 'PUT',
          headers: {
            ...requestHeaders(deviceId, newIdempotencyKey(`guided_${progressState}`)),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        },
      )
      setMessage(
        progressState === 'completed'
          ? 'Action completed. PartGraph recalculated the next verified action.'
          : progressState === 'skipped'
            ? 'Verified skippable action recorded as skipped.'
            : 'Problem recorded. PartGraph will not advance past this action.',
      )
      await loadSession(selectedId)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not update guided repair progress.'))
    } finally {
      setBusy(false)
    }
  }

  async function togglePlan() {
    if (!selectedId || !guidance) return
    if (showPlan) {
      setShowPlan(false)
      return
    }
    try {
      setBusy(true)
      setError(null)
      if (!plan) {
        setPlan(await apiRequest<GuidancePlan>(
          `/api/v1/repair-sessions/${selectedId}/guidance/plan`,
          {},
          { retryIdempotent: true },
        ))
      }
      setShowPlan(true)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not load the verified repair plan.'))
    } finally {
      setBusy(false)
    }
  }

  if (loading && sessions.length === 0) {
    return <section className="guided-workspace panel"><p>Loading verified repair guidance…</p></section>
  }

  return (
    <section className="guided-workspace panel" aria-label="Verified guided repair">
      <header className="guided-heading">
        <div>
          <p className="eyebrow">PARTGRAPH · VERIFIED GUIDANCE</p>
          <h1>Do the next verified action, not a guessed one.</h1>
          <p className="lede">
            PartGraph combines the exact repair definition, verified procedure evidence, dependencies,
            readiness, and your saved progress before it shows an action.
          </p>
        </div>
        {sessions.length > 0 && (
          <label className="guided-session-picker">
            <span>Repair session</span>
            <select
              value={selectedId}
              disabled={busy}
              onChange={(event) => void chooseSession(event.target.value)}
            >
              {sessions.map((item) => (
                <option key={item.id} value={item.id}>{item.title}</option>
              ))}
            </select>
          </label>
        )}
      </header>

      {error && <div className="repair-alert repair-alert--error">{error}</div>}
      {message && <div className="repair-alert repair-alert--success">{message}</div>}

      {sessions.length === 0 ? (
        <div className="guided-boundary guided-boundary--neutral">
          <strong>No active repair session.</strong>
          <p>Start a repair first. PartGraph will not create procedure context without one.</p>
          <button type="button" onClick={onStartRepair}>Start repair</button>
        </div>
      ) : boundary ? (
        <div className={`guided-boundary guided-boundary--${boundary.severity}`}>
          <span>{human(boundary.code)}</span>
          <strong>{boundary.title}</strong>
          <p>{boundary.detail}</p>
          {boundary.code === 'REPAIR_PROCEDURE_NOT_AVAILABLE' && (
            <div className="guided-controls">
              <button type="button" onClick={onOpenReadiness}>Open readiness</button>
              <small>New sessions offer verified repair binding during Start Repair. Existing unbound sessions can still be connected in Readiness.</small>
            </div>
          )}
        </div>
      ) : guidance ? (
        <>
          <div className="guided-meta">
            <div>
              <span>Verified repair</span>
              <strong>{guidance.repair_title}</strong>
              <small>v{guidance.version} · {human(guidance.definition_status)}</small>
            </div>
            <div>
              <span>Progress</span>
              <strong>{guidance.summary.completed + guidance.summary.skipped} / {guidance.summary.total}</strong>
              <small>{guidance.summary.blocked > 0 ? `${guidance.summary.blocked} blocked` : 'dependency-aware'}</small>
            </div>
            <div>
              <span>Guidance state</span>
              <strong>{human(guidance.status)}</strong>
              <small>{human(guidance.capability_policy_key)}</small>
            </div>
          </div>

          {guidance.procedure_complete ? (
            <div className="guided-complete">
              <span aria-hidden="true">✓</span>
              <div>
                <strong>Verified procedure complete.</strong>
                <p>All canonical actions in this version-pinned repair plan are completed or explicitly skippable-and-skipped.</p>
              </div>
            </div>
          ) : guidance.current_action ? (
            <CurrentAction
              action={guidance.current_action}
              guidanceStatus={guidance.status}
              canEdit={lease?.can_edit ?? false}
              busy={busy}
              onOpenReadiness={onOpenReadiness}
              onComplete={() => void updateProgress('completed')}
              onBlocked={() => void updateProgress('blocked')}
              onSkip={() => void updateProgress('skipped')}
            />
          ) : null}

          <AssistanceExplanation sessionId={selectedId} />

          <div className="guided-controls">
            {lease?.status === 'available' && (
              <button type="button" disabled={busy} onClick={() => void leaseAction(false)}>
                Take editing control
              </button>
            )}
            {lease?.status === 'held_by_other' && (
              <button type="button" disabled={busy} onClick={() => void leaseAction(true)}>
                Take over session
              </button>
            )}
            <button type="button" className="secondary" disabled={busy} onClick={() => void togglePlan()}>
              {showPlan ? 'Hide full plan' : 'View full verified plan'}
            </button>
            <span>{lease?.can_edit ? 'Editing on this device.' : `View only · ${human(lease?.status ?? 'available')}`}</span>
          </div>

          {showPlan && plan && <VerifiedPlan plan={plan} />}
        </>
      ) : null}
    </section>
  )
}

function CurrentAction({
  action,
  guidanceStatus,
  canEdit,
  busy,
  onOpenReadiness,
  onComplete,
  onBlocked,
  onSkip,
}: {
  action: GuidanceAction
  guidanceStatus: GuidanceStatus
  canEdit: boolean
  busy: boolean
  onOpenReadiness: () => void
  onComplete: () => void
  onBlocked: () => void
  onSkip: () => void
}) {
  const inventoryBlocked = guidanceStatus === 'inventory_blocked'
  const actionBlocked = guidanceStatus === 'action_blocked'

  return (
    <article className={`guided-action guided-action--${guidanceStatus}`}>
      <div className="guided-action-head">
        <div>
          <span>Current verified action · step {action.position + 1}</span>
          <h2>{action.title}</h2>
        </div>
        <b>{human(action.progress_state)}</b>
      </div>

      <p className="guided-instruction">{action.instruction}</p>

      {action.warning_text && <div className="guided-warning"><strong>Warning</strong><p>{action.warning_text}</p></div>}
      {action.workspace_note && <div className="guided-workspace-note"><strong>Before this action</strong><p>{action.workspace_note}</p></div>}
      {action.dependency_action_keys.length > 0 && <p className="guided-dependencies">Prerequisites complete: {action.dependency_action_keys.map(human).join(', ')}</p>}

      {action.inventory_blockers.length > 0 && (
        <div className="guided-blockers">
          <div>
            <strong>Readiness must be resolved before this action can complete.</strong>
            <button type="button" className="secondary" onClick={onOpenReadiness}>Open readiness</button>
          </div>
          <ul>
            {action.inventory_blockers.map((item) => (
              <li key={item.requirement_definition_id}>
                <span>{item.display_name}</span>
                <b>{quantityLabel(item)}</b>
              </li>
            ))}
          </ul>
        </div>
      )}

      {actionBlocked && (
        <div className="guided-problem">
          <strong>Work stopped here.</strong>
          <p>{action.notes ?? human(action.blocker_code ?? 'owner reported problem')}</p>
          <small>PartGraph will not advance until this current action is resolved.</small>
        </div>
      )}

      <div className="guided-action-buttons">
        <button type="button" disabled={busy || !canEdit || inventoryBlocked} onClick={onComplete}>
          {actionBlocked ? 'Problem resolved · complete action' : 'Complete action'}
        </button>
        {!actionBlocked && <button type="button" className="secondary" disabled={busy || !canEdit} onClick={onBlocked}>Problem / blocked</button>}
        {action.skippable && !actionBlocked && <button type="button" className="secondary" disabled={busy || !canEdit} onClick={onSkip}>Skip verified optional action</button>}
      </div>
      {!canEdit && <small className="guided-edit-note">Take editing control to record physical progress.</small>}
    </article>
  )
}

function VerifiedPlan({ plan }: { plan: GuidancePlan }) {
  return (
    <section className="guided-plan">
      <div className="guided-plan-head">
        <div><p className="eyebrow">FULL VERIFIED PLAN</p><h3>{plan.repair_title}</h3></div>
        <span>{plan.actions.length} actions</span>
      </div>
      <ol>
        {plan.actions.map((action) => (
          <li key={action.action_id} className={`guided-plan-item guided-plan-item--${action.progress_state}`}>
            <span>{action.position + 1}</span>
            <div>
              <strong>{action.title}</strong>
              <small>
                {human(action.progress_state)}
                {action.inventory_blockers.length > 0 ? ` · ${action.inventory_blockers.length} readiness blocker(s)` : ''}
                {action.dependency_action_keys.length > 0 ? ` · after ${action.dependency_action_keys.map(human).join(', ')}` : ''}
              </small>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
