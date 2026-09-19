import { apiRequest, AUTH_STATE_CLEARED_EVENT } from './api'

const PACK_KEY = 'partgraph:offline-repair-pack:v2'
const LEGACY_PACK_KEY = 'partgraph:offline-repair-pack:v1'
const LEGACY_OWNER_KEY = 'partgraph:offline-owner:v1'

let cacheEpoch = 0

type ResumeAttention = {
  kind: string
  id: string
  label: string
  state: string
  severity: string
  detail: string | null
}

type GuidanceAction = {
  action_id: string
  action_key: string
  title: string
  instruction: string
  warning_text: string | null
  workspace_note: string | null
  progress_state: 'pending' | 'completed' | 'skipped' | 'blocked'
  blocker_code: string | null
  notes: string | null
  dependency_action_keys: string[]
  inventory_blockers: Array<{ display_name: string; readiness_state: string }>
  completion_allowed: boolean
  boundary_code: string | null
}

export type OfflineRepairPack = {
  schema_version: 1
  pack_version: string
  read_only: true
  generated_at: string
  session_id: string
  server_sequence: number
  repair_definition_id: string
  repair_definition_version: number
  definition_status: string
  resume: {
    session: { id: string; title: string; status: string; current_sequence: number; updated_at: string }
    vehicle: {
      nickname: string | null
      identity: {
        year: number
        make: string
        model: string
        trim: string | null
        body_style: string | null
        engine: string | null
        transmission: string | null
        drivetrain: string | null
      }
    }
    reorientation: null | {
      checkpoint: { label: string; created_at: string }
      attention: ResumeAttention[]
      recent_activity: Array<{ sequence: number; label: string; created_at: string }>
      recent_observations: Array<{ id: string; category: string; text: string; created_at: string }>
      recent_evidence: Array<{ id: string; purpose: string; created_at: string }>
      counts: {
        fasteners_total: number
        hardware_not_installed: number
        hardware_stored: number
        hardware_loose: number
        supplemental_inventory_total: number
        verified_readiness_blockers: number
        observations_total: number
        photos_total: number
      }
      next_verified_action: { status: string; label: string | null; reason: string | null }
    }
  }
  readiness: {
    summary: { total: number; ready: number; missing: number; ordered: number; unavailable: number; blocked: number }
    requirements: Array<{
      requirement_definition_id: string
      category: string
      display_name: string
      required_quantity: string | number | null
      unit: string | null
      necessity: string
      quantity_available: string | number
      readiness_state: string
      readiness_source: string
      notes: string | null
    }>
  }
  guidance: {
    repair_title: string
    version: number
    definition_status: string
    status: string
    procedure_complete: boolean
    current_action: GuidanceAction | null
    summary: { total: number; completed: number; skipped: number; blocked: number; pending: number }
    actions: GuidanceAction[]
  }
}

type ServerOfflineRepairPack = OfflineRepairPack & { owner_id?: string }

function storage(): Storage | null {
  try { return window.sessionStorage } catch { return null }
}

function removeLegacyIdentityCache(): void {
  const target = storage()
  target?.removeItem(LEGACY_PACK_KEY)
  target?.removeItem(LEGACY_OWNER_KEY)
}

function privacyMinimizedPack(pack: ServerOfflineRepairPack): OfflineRepairPack {
  const { owner_id: _ownerId, ...offlinePack } = pack
  return offlinePack
}

export function cacheOfflineRepairPack(pack: ServerOfflineRepairPack): OfflineRepairPack {
  removeLegacyIdentityCache()
  const minimized = privacyMinimizedPack(pack)
  storage()?.setItem(PACK_KEY, JSON.stringify(minimized))
  return minimized
}

export function loadCachedOfflineRepairPack(_ownerId?: string | null, sessionId?: string | null): OfflineRepairPack | null {
  removeLegacyIdentityCache()
  const raw = storage()?.getItem(PACK_KEY)
  if (!raw) return null
  try {
    const pack = JSON.parse(raw) as OfflineRepairPack & { owner_id?: unknown; email?: unknown; username?: unknown }
    if (pack.schema_version !== 1 || pack.read_only !== true) return null
    if (pack.owner_id !== undefined || pack.email !== undefined || pack.username !== undefined) return null
    if (sessionId && pack.session_id !== sessionId) return null
    return pack
  } catch { return null }
}

export function invalidateOfflineRepairRefreshes(): void {
  cacheEpoch += 1
}

export function clearOfflineRepairCache(): void {
  invalidateOfflineRepairRefreshes()
  const target = storage()
  target?.removeItem(PACK_KEY)
  target?.removeItem(LEGACY_PACK_KEY)
  target?.removeItem(LEGACY_OWNER_KEY)
}

export async function refreshOfflineRepairPack(sessionId: string): Promise<OfflineRepairPack> {
  const requestEpoch = cacheEpoch
  const pack = await apiRequest<ServerOfflineRepairPack>(`/api/v1/repair-sessions/${sessionId}/offline-pack`)
  const minimized = privacyMinimizedPack(pack)
  if (requestEpoch !== cacheEpoch) return minimized
  return cacheOfflineRepairPack(pack)
}

removeLegacyIdentityCache()
window.addEventListener(AUTH_STATE_CLEARED_EVENT, clearOfflineRepairCache)
