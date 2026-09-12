import { ApiFailure, apiRequest, CSRF_HEADERS } from './api'
import { newIdempotencyKey, partGraphDeviceId } from './device'

export const repairDeviceId = partGraphDeviceId

const RECOVERY_DELAYS_MS = [0, 350, 1_000]

type MutationRecovery = {
  session_id: string
  idempotency_key: string
  state: 'committed' | 'unknown'
  event_type: string | null
  sequence: number | null
  committed_at: string | null
}

type CreationRecovery = {
  idempotency_key: string
  state: 'committed' | 'unknown'
  session_id: string | null
  created_at: string | null
}

export type RecoverableMutationResult<T> =
  | { kind: 'response'; value: T; idempotencyKey: string }
  | { kind: 'recovered'; value: null; idempotencyKey: string }

export type RecoverableCreationResult<T> =
  | { kind: 'response'; value: T; idempotencyKey: string }
  | { kind: 'recovered'; sessionId: string; idempotencyKey: string }

function headersForKey(
  idempotencyKey: string,
  options: { json?: boolean } = {},
): Record<string, string> {
  return {
    ...CSRF_HEADERS,
    'X-PartGraph-Device-ID': partGraphDeviceId(),
    'Idempotency-Key': idempotencyKey,
    ...(options.json ? { 'Content-Type': 'application/json' } : {}),
  }
}

export function repairMutationHeaders(options: { json?: boolean } = {}): Record<string, string> {
  return headersForKey(newIdempotencyKey('web'), options)
}

function ambiguousTransportFailure(error: unknown): error is ApiFailure {
  return error instanceof ApiFailure
    && (error.code === 'CLIENT_REQUEST_TIMEOUT' || error.code === 'CLIENT_NETWORK_FAILURE')
}

function uncertainWriteFailure(error: ApiFailure): ApiFailure {
  return new ApiFailure(
    'PartGraph could not confirm whether the change committed. Reload the repair before trying again.',
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

async function committedSessionMutation(
  sessionId: string,
  idempotencyKey: string,
): Promise<boolean> {
  for (const delay of RECOVERY_DELAYS_MS) {
    await wait(delay)
    try {
      const recovery = await apiRequest<MutationRecovery>(
        `/api/v1/repair-recovery/sessions/${sessionId}/mutations/${idempotencyKey}`,
        undefined,
        { retryIdempotent: true },
      )
      if (recovery.state === 'committed') return true
    } catch {
      // Recovery itself is best-effort. The caller will surface an uncertain-write state.
    }
  }
  return false
}

async function committedSessionCreation(idempotencyKey: string): Promise<string | null> {
  for (const delay of RECOVERY_DELAYS_MS) {
    await wait(delay)
    try {
      const recovery = await apiRequest<CreationRecovery>(
        `/api/v1/repair-recovery/session-creation/${idempotencyKey}`,
        undefined,
        { retryIdempotent: true },
      )
      if (recovery.state === 'committed' && recovery.session_id) return recovery.session_id
    } catch {
      // Recovery itself is best-effort. The caller will surface an uncertain-write state.
    }
  }
  return null
}

export async function recoverableRepairMutation<T>(
  sessionId: string,
  path: string,
  init: Omit<RequestInit, 'headers'> & { headers?: Record<string, string> } = {},
  options: { json?: boolean; prefix?: string } = {},
): Promise<RecoverableMutationResult<T>> {
  const idempotencyKey = newIdempotencyKey(options.prefix ?? 'web')
  const headers = {
    ...headersForKey(idempotencyKey, { json: options.json }),
    ...(init.headers ?? {}),
  }

  try {
    const value = await apiRequest<T>(path, { ...init, headers })
    return { kind: 'response', value, idempotencyKey }
  } catch (error) {
    if (!ambiguousTransportFailure(error)) throw error
    if (await committedSessionMutation(sessionId, idempotencyKey)) {
      return { kind: 'recovered', value: null, idempotencyKey }
    }
    throw uncertainWriteFailure(error)
  }
}

export async function recoverableRepairSessionCreation<T>(
  path: string,
  init: Omit<RequestInit, 'headers'> & { headers?: Record<string, string> } = {},
  options: { json?: boolean; prefix?: string } = {},
): Promise<RecoverableCreationResult<T>> {
  const idempotencyKey = newIdempotencyKey(options.prefix ?? 'start_repair')
  const headers = {
    ...headersForKey(idempotencyKey, { json: options.json }),
    ...(init.headers ?? {}),
  }

  try {
    const value = await apiRequest<T>(path, { ...init, headers })
    return { kind: 'response', value, idempotencyKey }
  } catch (error) {
    if (!ambiguousTransportFailure(error)) throw error
    const sessionId = await committedSessionCreation(idempotencyKey)
    if (sessionId) return { kind: 'recovered', sessionId, idempotencyKey }
    throw uncertainWriteFailure(error)
  }
}
