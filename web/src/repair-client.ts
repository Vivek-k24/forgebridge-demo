import { CSRF_HEADERS } from './api'

const DEVICE_STORAGE_KEY = 'partgraph:device-id'

function randomUuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export function repairDeviceId(): string {
  const existing = window.localStorage.getItem(DEVICE_STORAGE_KEY)
  if (existing) return existing
  const created = randomUuid()
  window.localStorage.setItem(DEVICE_STORAGE_KEY, created)
  return created
}

export function repairMutationHeaders(options: { json?: boolean } = {}): Record<string, string> {
  return {
    ...CSRF_HEADERS,
    'X-PartGraph-Device-ID': repairDeviceId(),
    'Idempotency-Key': randomUuid(),
    ...(options.json ? { 'Content-Type': 'application/json' } : {}),
  }
}
