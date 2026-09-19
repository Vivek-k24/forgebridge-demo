import { useEffect, useState, type ReactNode } from 'react'
import { activeRepairSessionId, ACTIVE_REPAIR_SESSION_EVENT } from './active-repair'
import { AUTH_STATE_CLEARED_EVENT, probeApiAvailability, REPAIR_API_MUTATION_EVENT } from './api'
import { OfflineRepairWorkspace } from './OfflineRepair'
import { invalidateOfflineRepairRefreshes, loadCachedOfflineRepairPack, refreshOfflineRepairPack, type OfflineRepairPack } from './offline-repair'
import { REPAIR_STATE_CHANGED_EVENT } from './repair-client'
import './offline-continuity.css'

const SECTIONS = ['resume', 'readiness', 'guidance', 'completion', 'log'] as const
type Section = (typeof SECTIONS)[number]

function currentSection(): Section {
  const value = window.location.hash.replace(/^#\/?/, '') as Section
  return SECTIONS.includes(value) ? value : 'resume'
}

export default function OfflineContinuity({ children }: { children: ReactNode }) {
  const [offline, setOffline] = useState(false)
  const [section, setSection] = useState<Section>(currentSection)
  const [pack, setPack] = useState<OfflineRepairPack | null>(null)

  useEffect(() => {
    let active = true
    let syncGeneration = 0
    let syncTimer: number | null = null

    async function sync(generation: number) {
      const sessionId = activeRepairSessionId()
      const status = await probeApiAvailability()
      if (!active || generation !== syncGeneration) return

      setOffline(status.state !== 'ready')
      if (!sessionId) {
        setPack(null)
        return
      }

      const cached = loadCachedOfflineRepairPack(null, sessionId)
      if (cached) setPack(cached)
      if (status.state !== 'ready') return

      try {
        const fresh = await refreshOfflineRepairPack(sessionId)
        if (!active || generation !== syncGeneration || navigator.onLine === false) return
        setPack(fresh)
      } catch {
        /* keep the last confirmed pack */
      }
    }

    function scheduleSync(delay = 100) {
      syncGeneration += 1
      invalidateOfflineRepairRefreshes()
      const generation = syncGeneration
      if (syncTimer !== null) window.clearTimeout(syncTimer)
      syncTimer = window.setTimeout(() => {
        syncTimer = null
        void sync(generation)
      }, delay)
    }

    const changed = () => scheduleSync()
    const clear = () => setPack(null)
    const hash = () => setSection(currentSection())
    scheduleSync(0)
    const timer = window.setInterval(() => scheduleSync(0), 30_000)
    window.addEventListener('online', changed)
    window.addEventListener('offline', changed)
    window.addEventListener(ACTIVE_REPAIR_SESSION_EVENT, changed)
    window.addEventListener(REPAIR_STATE_CHANGED_EVENT, changed)
    window.addEventListener(REPAIR_API_MUTATION_EVENT, changed)
    window.addEventListener(AUTH_STATE_CLEARED_EVENT, clear)
    window.addEventListener('hashchange', hash)
    return () => {
      active = false
      syncGeneration += 1
      invalidateOfflineRepairRefreshes()
      if (syncTimer !== null) window.clearTimeout(syncTimer)
      window.clearInterval(timer)
      window.removeEventListener('online', changed)
      window.removeEventListener('offline', changed)
      window.removeEventListener(ACTIVE_REPAIR_SESSION_EVENT, changed)
      window.removeEventListener(REPAIR_STATE_CHANGED_EVENT, changed)
      window.removeEventListener(REPAIR_API_MUTATION_EVENT, changed)
      window.removeEventListener(AUTH_STATE_CLEARED_EVENT, clear)
      window.removeEventListener('hashchange', hash)
    }
  }, [])

  if (!offline || !pack) return <>{children}</>
  return (
    <div className="offline-continuity-shell">
      <div className="offline-continuity-banner"><strong>Offline repair pack · read only</strong><span>Last sync {new Date(pack.generated_at).toLocaleString()} · definition v{pack.repair_definition_version}</span></div>
      <nav className="offline-continuity-nav">{SECTIONS.map((item) => <button key={item} type="button" onClick={() => { window.location.hash = `#/${item}`; setSection(item) }}>{item === 'resume' ? 'Overview' : item}</button>)}</nav>
      <OfflineRepairWorkspace pack={pack} section={section} />
    </div>
  )
}
