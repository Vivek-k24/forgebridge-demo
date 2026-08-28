const DEVICE_ID_KEY = 'partgraph.device-id'

export function partGraphDeviceId(): string {
  const existing = window.localStorage.getItem(DEVICE_ID_KEY)
  if (existing) return existing

  const created = crypto.randomUUID()
  window.localStorage.setItem(DEVICE_ID_KEY, created)
  return created
}

export function newIdempotencyKey(prefix: string): string {
  const random = crypto.randomUUID().replaceAll('-', '')
  return `${prefix}_${random}`.slice(0, 64)
}
