import { useCallback, useEffect, useMemo, useState } from 'react'
import { activeRepairSessionId, preferredRepairSessionId, setActiveRepairSessionId } from './active-repair'
import { AssistanceExplanation } from './AssistanceExplanation'
import { ApiFailure, apiRequest, CSRF_HEADERS, formatApiFailure } from './api'
import { partGraphDeviceId } from './device'
import { recoverableRepairMutation } from './repair-client'
import './guided-repair.css'

type SessionStatus = 'active' | 'paused' | 'archived'
type LeaseStatus = 'available' | 'owned' | 'held_by_other'
type ProgressState = 'pending' | 'completed' | 'skipped' | 'blocked'
type GuidanceStatus = 'action_available' | 'action_blocked' | 'inventory_blocked' | 'unsupported_boundary' | 'procedure_complete'

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
  completion_allowed: boolean
  boundary_code: string | null
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

function requestHeaders(deviceId: string): Record<string, string> {
  return {
    ...CSRF_HEADERS,
    'X-PartGraph-Device-ID': deviceId,
  }
}

function human(value: string): string {
  return value.replaceAll('_', ' ').replaceAll('-', ' ')
}

function guidanceStatusLabel(status: GuidanceStatus): string {
  if (status === 'action_available') return 'Ready for the next step'
  if (status === 'action_blocked') return 'Stopped at the current step'
  if (status === 'inventory_blocked') return 'An item is needed first'
  if (status === 'unsupported_boundary') return 'Outside PartGraph support'
  return 'Supported steps complete'
}

function progressStateLabel(state: ProgressState): string {
  if (state === 'completed') return 'Complete'
  if (state === 'skipped') return 'Skipped'
  if (state === 'blocked') return 'Blocked'
  return 'Not started'
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
    if (!selectedId || !action || !action.completion_allowed) return
    try {
      setBusy(true)
      setError(null)
      setMessage(null)
      const payload = progressState === 'blocked'
        ? { progress_state: progressState, blocker_code: 'owner_reported_problem' }
        : { progress_state: progressState }
      await recoverableRepairMutation<Guidance>(
        selectedId,
        `/api/v1/repair-sessions/${selectedId}/guidance/actions/${action.action_id}`,
        {
          method: 'PUT',
          body: JSON.stringify(payload),
        },
        { json: true, prefix: `guided_${progressState}` },
      )
      setMessage(
        progressState === 'completed'
          ? 'Step complete. PartGraph recalculated what comes next.'
          : progressState === 'skipped'
            ? 'Optional step recorded as skipped.'
            : 'Problem recorded. PartGraph will not move past this step.',
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

  const resolvedSteps = guidance ? guidance.summary.completed + guidance.summary.skipped : 0
  const progressPercent = guidance && guidance.summary.total > 0
    ? Math.round((resolvedSteps / guidance.summary.total) * 100)
    : 0

  return (
    <section className="guided-workspace panel" aria-label="Verified guided repair">
      <header className="guided-heading">
        <div>
          <p className="eyebrow">PARTGRAPH · GUIDED REPAIR</p>
          <h1>Focus on what you need to do next.</h1>
          <p className="lede">
            PartGraph checks the repair plan, what must happen first, what you already have, and what
            you have completed before showing the next supported step.
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
          <strong>No repair session is open.</strong>
          <p>Start a repair first so PartGraph knows which vehicle and repair state it is working with.</p>
          <button type="button" onClick={onStartRepair}>Start repair</button>
        </div>
      ) : boundary ? (
        <div className={`guided-boundary guided-boundary--${boundary.severity}`}>
          <strong>{boundary.title}</strong>
          <p>{boundary.detail}</p>
          {boundary.code === 'REPAIR_PROCEDURE_NOT_AVAILABLE' && (
            <div className="guided-controls">
              <button type="button" onClick={onOpenReadiness}>Open readiness</button>
              <small>This session can still track repair state even when verified step-by-step guidance is not available.</small>
            </div>
          )}
        </div>
      ) : guidance ? (
        <>
          <div className="guided-meta">
            <div>
              <span>Repair</span>
              <strong>{guidance.repair_title}</strong>
              <small>Verified repair data · version {guidance.version}</small>
            </div>
            <div>
              <span>Progress</span>
              <strong>{resolvedSteps} of {guidance.summary.total} steps resolved</strong>
              <div className="guided-progress-track" aria-label={`${progressPercent}% of supported steps resolved`}>
                <i style={{ width: `${progressPercent}%` }} />
              </div>
            </div>
            <div>
              <span>Current status</span>
              <strong>{guidanceStatusLabel(guidance.status)}</strong>
              <small>{guidance.summary.blocked > 0 ? `${guidance.summary.blocked} step blocked` : 'PartGraph checks before advancing'}</small>
            </div>
          </div>

          {guidance.procedure_complete ? (
            <div className="guided-complete">
              <span aria-hidden="true">✓</span>
              <div>
                <strong>PartGraph-supported steps are complete.</strong>
                <p>The verified steps represented in this repair plan are resolved. PartGraph does not use this state to hide a known unsupported required step.</p>
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
              {showPlan ? 'Hide repair plan' : 'View repair plan'}
            </button>
            <span>{lease?.can_edit ? 'Progress can be recorded on this device.' : 'View only until editing control is available.'}</span>
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
  const unsupportedBoundary = guidanceStatus === 'unsupported_boundary' || !action.completion_allowed

  return (
    <article className={`guided-action guided-action--${guidanceStatus}`}>
      <div className="guided-action-head">
        <div>
          <span>{unsupportedBoundary ? 'Required work outside PartGraph support' : `Step ${action.position + 1} · what to do now`}</span>
          <h2>{action.title}</h2>
        </div>
        <b>{unsupportedBoundary ? 'Outside support' : progressStateLabel(action.progress_state)}</b>
      </div>

      <p className="guided-instruction">{action.instruction}</p>

      {action.warning_text && <div className="guided-warning"><strong>Warning</strong><p>{action.warning_text}</p></div>}
      {action.workspace_note && <div className="guided-workspace-note"><strong>Before this step</strong><p>{action.workspace_note}</p></div>}
      {action.dependency_action_keys.length > 0 && <p className="guided-dependencies">The required earlier step{action.dependency_action_keys.length === 1 ? '' : 's'} for this action are already resolved.</p>}

      {unsupportedBoundary && (
        <div className="guided-boundary guided-boundary--professional">
          <strong>PartGraph stops step-by-step guidance here.</strong>
          <p>This required work remains part of the repair, but PartGraph does not support performing or marking it complete inside the guided workflow.</p>
        </div>
      )}

      {!unsupportedBoundary && action.inventory_blockers.length > 0 && (
        <div className="guided-blockers">
          <div>
            <strong>You need to resolve these items before completing this step.</strong>
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

      {!unsupportedBoundary && actionBlocked && (
        <div className="guided-problem">
          <strong>Work stopped here.</strong>
          <p>{action.notes ?? 'A problem was recorded at this step.'}</p>
          <small>PartGraph will not move to the next step until this one is resolved.</small>
        </div>
      )}

      {!unsupportedBoundary && (
        <div className="guided-action-buttons">
          <button type="button" disabled={busy || !canEdit || inventoryBlocked} onClick={onComplete}>
            {actionBlocked ? 'Problem resolved · complete step' : 'Complete step'}
          </button>
          {!actionBlocked && <button type="button" className="secondary" disabled={busy || !canEdit} onClick={onBlocked}>I hit a problem</button>}
          {action.skippable && !actionBlocked && <button type="button" className="secondary" disabled={busy || !canEdit} onClick={onSkip}>Skip optional step</button>}
        </div>
      )}
      {!unsupportedBoundary && !canEdit && <small className="guided-edit-note">Take editing control to record progress.</small>}
    </article>
  )
}

function VerifiedPlan({ plan }: { plan: GuidancePlan }) {
  return (
    <section className="guided-plan">
      <div className="guided-plan-head">
        <div><p className="eyebrow">REPAIR PLAN</p><h3>{plan.repair_title}</h3></div>
        <span>{plan.actions.length} steps</span>
      </div>
      <ol>
        {plan.actions.map((action) => (
          <li key={action.action_id} className={`guided-plan-item guided-plan-item--${action.progress_state}`}>
            <span>{action.position + 1}</span>
            <div>
              <strong>{action.title}</strong>
              <small>
                {action.completion_allowed ? progressStateLabel(action.progress_state) : 'Outside PartGraph support'}
                {action.inventory_blockers.length > 0 ? ` · ${action.inventory_blockers.length} item blocker${action.inventory_blockers.length === 1 ? '' : 's'}` : ''}
                {action.dependency_action_keys.length > 0 ? ` · ${action.dependency_action_keys.length} earlier required step${action.dependency_action_keys.length === 1 ? '' : 's'}` : ''}
              </small>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
