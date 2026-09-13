import { apiRequest, AUTH_STATE_CLEARED_EVENT } from './api'

const PACK_KEY = 'partgraph:offline-repair-pack:v1'
const OWNER_KEY = 'partgraph:offline-owner:v1'

export type OfflineOwner = { id: string; email: string; username: string }

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
  owner_id: string
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

function storage(): Storage | null {
  try { return window.sessionStorage } catch { return null }
}

export function rememberOfflineOwner(owner: OfflineOwner): void {
  storage()?.setItem(OWNER_KEY, JSON.stringify(owner))
}

export function cachedOfflineOwner(): OfflineOwner | null {
  const raw = storage()?.getItem(OWNER_KEY)
  if (!raw) return null
  try {
    const value = JSON.parse(raw) as Partial<OfflineOwner>
    return value.id && value.email && value.username
      ? { id: value.id, email: value.email, username: value.username }
      : null
  } catch { return null }
}

export function cacheOfflineRepairPack(pack: OfflineRepairPack): void {
  storage()?.setItem(PACK_KEY, JSON.stringify(pack))
}

export function loadCachedOfflineRepairPack(ownerId?: string | null, sessionId?: string | null): OfflineRepairPack | null {
  const raw = storage()?.getItem(PACK_KEY)
  if (!raw) return null
  try {
    const pack = JSON.parse(raw) as OfflineRepairPack
    if (pack.schema_version !== 1 || pack.read_only !== true) return null
    if (ownerId && pack.owner_id !== ownerId) return null
    if (sessionId && pack.session_id !== sessionId) return null
    return pack
  } catch { return null }
}

export function hasOfflineRepairPackForOwner(ownerId: string): boolean {
  return loadCachedOfflineRepairPack(ownerId) !== null
}

export function clearOfflineRepairCache(): void {
  storage()?.removeItem(PACK_KEY)
  storage()?.removeItem(OWNER_KEY)
}

export async function refreshOfflineRepairPack(sessionId: string): Promise<OfflineRepairPack> {
  const pack = await apiRequest<OfflineRepairPack>(`/api/v1/repair-sessions/${sessionId}/offline-pack`)
  cacheOfflineRepairPack(pack)
  return pack
}

window.addEventListener(AUTH_STATE_CLEARED_EVENT, clearOfflineRepairCache)
