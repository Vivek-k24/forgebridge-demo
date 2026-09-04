const ACTIVE_REPAIR_SESSION_KEY = 'partgraph:active-repair-session'
export const ACTIVE_REPAIR_SESSION_EVENT = 'partgraph:active-repair-session-changed'

export function activeRepairSessionId(): string | null {
  return window.sessionStorage.getItem(ACTIVE_REPAIR_SESSION_KEY)
}

export function setActiveRepairSessionId(sessionId: string | null): void {
  if (sessionId) {
    window.sessionStorage.setItem(ACTIVE_REPAIR_SESSION_KEY, sessionId)
  } else {
    window.sessionStorage.removeItem(ACTIVE_REPAIR_SESSION_KEY)
  }
  window.dispatchEvent(new CustomEvent(ACTIVE_REPAIR_SESSION_EVENT, { detail: { sessionId } }))
}

export function preferredRepairSessionId<T extends { id: string }>(rows: T[], current?: string | null): string {
  const stored = activeRepairSessionId()
  if (stored && rows.some((row) => row.id === stored)) return stored
  if (current && rows.some((row) => row.id === current)) return current
  return rows[0]?.id ?? ''
}
