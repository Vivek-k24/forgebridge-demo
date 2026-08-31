const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')
const HARD_TIMEOUT_MS = 10_000
const EXPECTED_API_VERSION = 'v1'

export const CSRF_HEADERS = { 'X-PartGraph-CSRF': '1' }

type ErrorEnvelope = {
  error?: {
    code?: string
    message?: string
    request_id?: string
    retryable?: boolean
  }
}

export class ApiFailure extends Error {
  code: string
  requestId: string | null
  retryable: boolean
  status: number | null

  constructor(
    message: string,
    options: { code: string; requestId?: string | null; retryable?: boolean; status?: number | null },
  ) {
    super(message)
    this.name = 'ApiFailure'
    this.code = options.code
    this.requestId = options.requestId ?? null
    this.retryable = options.retryable ?? false
    this.status = options.status ?? null
  }
}

function clientRequestId(): string {
  return crypto.randomUUID().replaceAll('-', '')
}

async function sleep(milliseconds: number) {
  await new Promise((resolve) => window.setTimeout(resolve, milliseconds))
}

export function formatApiFailure(error: unknown, fallback: string): string {
  if (!(error instanceof ApiFailure)) return `${fallback} [CLIENT_UNKNOWN_FAILURE]`
  const request = error.requestId ? ` · request ${error.requestId}` : ''
  return `${error.message} [${error.code}${request}]`
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  options: { retryIdempotent?: boolean } = {},
): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const retryIdempotent = options.retryIdempotent ?? method === 'GET'
  const attempts = retryIdempotent ? 2 : 1
  let lastFailure: ApiFailure | null = null

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), HARD_TIMEOUT_MS)
    const requestId = clientRequestId()

    try {
      const response = await fetch(`${API_BASE_URL}${path}`, {
        ...init,
        credentials: 'include',
        headers: {
          ...init.headers,
          'X-Request-ID': requestId,
        },
        signal: controller.signal,
      })
      const responseRequestId = response.headers.get('x-request-id') ?? requestId
      const apiVersion = response.headers.get('x-partgraph-api-version')
      if (!apiVersion) {
        throw new ApiFailure('PartGraph received a response without an API version.', {
          code: 'CLIENT_API_VERSION_MISSING',
          requestId: responseRequestId,
          status: response.status,
        })
      }
      if (apiVersion !== EXPECTED_API_VERSION) {
        throw new ApiFailure('Client and API versions do not match.', {
          code: 'CLIENT_API_VERSION_MISMATCH',
          requestId: responseRequestId,
          status: response.status,
        })
      }

      if (!response.ok) {
        let envelope: ErrorEnvelope
        try {
          envelope = (await response.json()) as ErrorEnvelope
        } catch {
          throw new ApiFailure(`API returned HTTP ${response.status} without a valid error envelope.`, {
            code: 'CLIENT_ERROR_ENVELOPE_INVALID',
            requestId: responseRequestId,
            retryable: response.status >= 500,
            status: response.status,
          })
        }
        throw new ApiFailure(envelope.error?.message ?? `API returned HTTP ${response.status}.`, {
          code: envelope.error?.code ?? `HTTP_${response.status}`,
          requestId: envelope.error?.request_id ?? responseRequestId,
          retryable: envelope.error?.retryable ?? response.status >= 500,
          status: response.status,
        })
      }

      if (response.status === 204) return undefined as T
      return (await response.json()) as T
    } catch (error) {
      if (error instanceof ApiFailure) {
        lastFailure = error
      } else if (error instanceof DOMException && error.name === 'AbortError') {
        lastFailure = new ApiFailure('The request reached PartGraph’s 10-second blocking limit.', {
          code: 'CLIENT_REQUEST_TIMEOUT',
          requestId,
          retryable: true,
        })
      } else {
        lastFailure = new ApiFailure('PartGraph could not reach the API.', {
          code: 'CLIENT_NETWORK_FAILURE',
          requestId,
          retryable: true,
        })
      }
    } finally {
      window.clearTimeout(timeout)
    }

    if (!lastFailure.retryable || attempt + 1 >= attempts) break
    await sleep(250)
  }

  throw lastFailure ?? new ApiFailure('Unknown client failure.', { code: 'CLIENT_UNKNOWN_FAILURE' })
}
