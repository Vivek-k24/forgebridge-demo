import { CSRF_HEADERS } from './api'
import { newIdempotencyKey, partGraphDeviceId } from './device'

export const repairDeviceId = partGraphDeviceId

export function repairMutationHeaders(options: { json?: boolean } = {}): Record<string, string> {
  return {
    ...CSRF_HEADERS,
    'X-PartGraph-Device-ID': partGraphDeviceId(),
    'Idempotency-Key': newIdempotencyKey('web'),
    ...(options.json ? { 'Content-Type': 'application/json' } : {}),
  }
}
