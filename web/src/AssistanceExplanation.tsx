import { useEffect, useState } from 'react'
import { apiRequest, formatApiFailure } from './api'
import './assistance-explanation.css'

type AssistanceReason =
  | 'next_verified_action'
  | 'current_action_inventory_blocked'
  | 'current_action_physically_blocked'
  | 'verified_procedure_complete'

type AssistanceAction = {
  action_id: string
  action_key: string
  title: string
  dependency_action_keys: string[]
  supporting_claim_ids: string[]
}

type AssistanceBlocker = {
  requirement_definition_id: string
  requirement_key: string
  display_name: string
  readiness_state: string
  required_quantity: string | null
  unit: string | null
}

type AssistanceExplanationResponse = {
  session_id: string
  repair_definition_id: string
  repair_key: string
  version: number
  guidance_status: string
  mode: 'deterministic'
  ai_invoked: false
  reason_code: AssistanceReason
  headline: string
  explanation: string
  current_action: AssistanceAction | null
  inventory_blockers: AssistanceBlocker[]
}

export function AssistanceExplanation({ sessionId }: { sessionId: string }) {
  const [explanation, setExplanation] = useState<AssistanceExplanationResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setExplanation(null)
    setError(null)
  }, [sessionId])

  async function explain() {
    try {
      setLoading(true)
      setError(null)
      const response = await apiRequest<AssistanceExplanationResponse>(
        `/api/v1/repair-sessions/${sessionId}/assistance/explanation`,
        {},
        { retryIdempotent: true },
      )
      setExplanation(response)
    } catch (failure) {
      setError(formatApiFailure(failure, 'Could not explain the current verified state.'))
    } finally {
      setLoading(false)
    }
  }

  if (!explanation) {
    return (
      <div className="assistance-entry">
        <button type="button" className="secondary" disabled={loading} onClick={() => void explain()}>
          {loading ? 'Explaining verified state…' : 'Why this step?'}
        </button>
        <span>Uses the verified repair state first. No AI model is needed for this explanation.</span>
        {error && <p className="assistance-error">{error}</p>}
      </div>
    )
  }

  return (
    <aside className="assistance-explanation" aria-label="Why this verified repair state">
      <div className="assistance-explanation__head">
        <div>
          <span>WHY THIS STATE</span>
          <strong>{explanation.headline}</strong>
        </div>
        <b>Deterministic</b>
      </div>
      <p>{explanation.explanation}</p>
      {explanation.inventory_blockers.length > 0 && (
        <ul>
          {explanation.inventory_blockers.map((item) => (
            <li key={item.requirement_definition_id}>
              <span>{item.display_name}</span>
              <b>{item.readiness_state.replaceAll('_', ' ')}</b>
            </li>
          ))}
        </ul>
      )}
      <footer>
        <span>AI invoked: no</span>
        <span>Reason: {explanation.reason_code.replaceAll('_', ' ')}</span>
        <button type="button" className="link-button" disabled={loading} onClick={() => void explain()}>
          Refresh explanation
        </button>
      </footer>
      {error && <p className="assistance-error">{error}</p>}
    </aside>
  )
}
