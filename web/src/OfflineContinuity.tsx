import { useEffect, useState, type ReactNode } from 'react'
import { activeRepairSessionId, ACTIVE_REPAIR_SESSION_EVENT } from './active-repair'
import { probeApiAvailability } from './api'
import { OfflineRepairWorkspace } from './OfflineRepair'
import { loadCachedOfflineRepairPack, refreshOfflineRepairPack, type OfflineRepairPack } from './offline-repair'

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
    async function sync() {
      const sessionId = activeRepairSessionId()
      const status = await probeApiAvailability()
      if (!active) return
      setOffline(status.state !== 'ready')
      if (!sessionId) { setPack(null); return }
      const cached = loadCachedOfflineRepairPack(null, sessionId)
      if (cached) setPack(cached)
      if (status.state === 'ready') {
        try {
          const fresh = await refreshOfflineRepairPack(sessionId)
          if (active) setPack(fresh)
        } catch { /* keep last confirmed pack */ }
      }
    }
    const changed = () => { window.setTimeout(() => void sync(), 100) }
    const hash = () => setSection(currentSection())
    void sync()
    const timer = window.setInterval(() => void sync(), 30_000)
    window.addEventListener('online', changed)
    window.addEventListener('offline', changed)
    window.addEventListener(ACTIVE_REPAIR_SESSION_EVENT, changed)
    window.addEventListener('hashchange', hash)
    return () => {
      active = false
      window.clearInterval(timer)
      window.removeEventListener('online', changed)
      window.removeEventListener('offline', changed)
      window.removeEventListener(ACTIVE_REPAIR_SESSION_EVENT, changed)
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
